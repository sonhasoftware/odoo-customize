# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.ai.utils.llm_providers import get_provider_for_embedding_model, PROVIDERS


@tagged("-at_install", "post_install")
class TestGeminiIntegration(TransactionCase):
    """Test suite for Gemini API integration"""

    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param(
            "ai.google_key", "test-gemini-key"
        )
        self.agent = self.env["ai.agent"].create(
            {
                "name": "Test Gemini Agent",
                "llm_model": "gemini-1.5-flash",
                "response_style": "analytical",
            }
        )
        test_attachment = self.env["ir.attachment"].create(
            {
                "name": "test_doc.txt",
                "index_content": "Odoo is an open-source ERP system with many modules.",
                "res_model": "ai.agent",
                "res_id": self.agent.id,
            }
        )
        self.agent_source = self.env["ai.agent.source"].create(
            {
                "name": "Test Document",
                "agent_id": self.agent.id,
                "type": "binary",
                "attachment_id": test_attachment.id,
                "status": "indexed",
                "is_active": True,
            }
        )
        self.test_embedding = self.env["ai.embedding"].create(
            {
                "attachment_id": test_attachment.id,
                "content": test_attachment.index_content,
                "embedding_model": "gemini-embedding-001",
                "embedding_vector": [0.1] * 1536,
                "sequence": 1,
            }
        )

    @patch("odoo.addons.ai.models.ai_embedding.AIEmbedding._get_similar_chunks")
    @patch("odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token")
    @patch("odoo.addons.ai.utils.llm_api_service.LLMApiService._request")
    def test_gemini_embedding_and_completion(
        self, mock_request, mock_get_api_token, mock_get_similar_chunks
    ):
        """Test that Gemini models use correct API endpoints and models for embeddings and completions with RAG"""
        mock_get_api_token.return_value = "test-gemini-key"
        mock_get_similar_chunks.return_value = self.test_embedding

        api_calls = []

        def mock_request_handler(method, endpoint, headers, body, params=None, **kwargs):
            api_calls.append(
                {
                    "endpoint": endpoint,
                    "headers": headers,
                    "body": body,
                }
            )
            if endpoint == "/embeddings":
                self.assertEqual(body["model"], "gemini-embedding-001")
                self.assertEqual(headers["Authorization"], "Bearer test-gemini-key")
                if body["input"] == "What is Odoo?":
                    return {
                        "data": [
                            {
                                "embedding": [0.4] * 1536,
                                "index": 0,
                                "object": "embedding",
                            }
                        ],
                        "model": "gemini-embedding-001",
                    }
            elif endpoint.startswith("/models/"):
                self.assertIn("gemini-1.5-flash", endpoint)
                self.assertEqual(body.get("generationConfig", {}).get("temperature"), 0.2)
                self.assertEqual(params.get("key"), "test-gemini-key")

                instructions = body["systemInstruction"]
                rag_context_found = "##Context information:" in str(instructions["parts"])
                self.assertTrue(rag_context_found, "RAG context not found in messages")
                self.assertIn(
                    "Odoo is an open-source ERP system", str(instructions["parts"])
                )

                return {
                    "candidates": [
                        {
                            "content": {
                                "role": "assistant",
                                "parts": [{"text": "Odoo is an open-source ERP system as mentioned in the documents."}],
                            },
                        }
                    ],
                }
            return {}

        mock_request.side_effect = mock_request_handler

        response = self.agent._generate_response("What is Odoo?")

        self.assertIsInstance(response, list)
        self.assertIn("open-source ERP", response[0])

        self.assertEqual(len(api_calls), 2)
        self.assertEqual(api_calls[0]["endpoint"], "/embeddings")
        self.assertEqual(api_calls[0]["body"]["input"], "What is Odoo?")
        self.assertEqual(api_calls[1]["endpoint"], "/models/gemini-1.5-flash:generateContent")

    def test_provider_detection_for_gemini(self):
        """Test that Gemini models correctly identify Google as provider and use correct embedding model"""
        google_provider = next(p for p in PROVIDERS if p.name == "google")
        for model, _ in google_provider.llms:
            self.agent.llm_model = model
            self.assertEqual(self.agent._get_provider(), "google")
            self.assertEqual(self.agent._get_embedding_model(), "gemini-embedding-001")

        self.assertEqual(get_provider_for_embedding_model(self.env, "gemini-embedding-001"), "google")

        # Test that unknown embedding model raises an error
        with self.assertRaises(UserError):
            get_provider_for_embedding_model(self.env, "unknown-embedding-model")
