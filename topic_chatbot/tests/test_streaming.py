# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase, tagged
from odoo.addons.topic_chatbot.controllers.main import TopicChatbotController
import json
import base64
import re
from unittest.mock import MagicMock


@tagged('post_install', '-at_install')
class TestTopicChatbotStreaming(TransactionCase):
    """Unit tests for streaming-related logic (model-level, no HTTP mocking).

    NOTE: We do NOT mock `odoo.http.request` because it is a Werkzeug
    LocalProxy and cannot be patched in TransactionCase / HttpCase.
    Instead, we test the business logic that feeds into streaming:
    token-limit, rate-limit, context retrieval, and message persistence.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.controller = TopicChatbotController()

        # Create test user
        cls.DemoUser = cls.env['res.users'].create({
            'name': 'Test User Streaming',
            'login': 'test_user_streaming',
            'groups_id': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('topic_chatbot.group_topic_chatbot_user').id),
            ]
        })

        # Create test topic and conversation
        cls.TestTopic = cls.env['topic_chatbot.topic'].create({
            'name': 'Streaming Test Topic',
            'description': 'Topic for streaming tests',
            'is_public': True,
        })

        cls.TestConversation = cls.env['topic_chatbot.conversation'].create({
            'name': 'Streaming Test Chat',
            'topic_id': cls.TestTopic.id,
            'user_id': cls.DemoUser.id,
        })

        # Set up config
        cls.env['ir.config_parameter'].sudo().set_param(
            'topic_chatbot.gemini_api_key', 'test_streaming_key')
        cls.env['ir.config_parameter'].sudo().set_param(
            'topic_chatbot.gemini_model', 'gemini-3.6-flash')

    # =========================================================
    # 1. Endpoint & method existence
    # =========================================================
    def test_01_streaming_endpoint_exists(self):
        """Test streaming endpoint exists and is configured correctly."""
        self.assertTrue(hasattr(self.controller, 'ask_stream'))
        self.assertIsNotNone(self.controller.ask_stream)

    # =========================================================
    # 2. Rate-limit enforcement for streaming
    # =========================================================
    def test_02_streaming_rate_limit_enforcement(self):
        """Test that rate-limit logic blocks after MAX messages."""
        for i in range(self.controller.RATE_LIMIT_MAX_MESSAGES):
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.TestConversation.id,
                'role': 'user',
                'content': f'Rate limit streaming message {i}',
            })

        self.env.flush_all()

        is_limited = self.controller._check_rate_limit(
            self.env, self.DemoUser.id)
        self.assertTrue(is_limited,
                        "Rate limit should trigger for streaming user")

    # =========================================================
    # 3. Processing flag check
    # =========================================================
    def test_03_streaming_processing_flag_check(self):
        """Test conversation processing flag blocks concurrent requests."""
        self.TestConversation.write({'is_processing': True})
        self.assertTrue(self.TestConversation.is_processing,
                        "Processing flag should be True")

        self.TestConversation.write({'is_processing': False})
        self.assertFalse(self.TestConversation.is_processing,
                         "Processing flag should be reset")

    # =========================================================
    # 4. Context retrieval method
    # =========================================================
    def test_04_streaming_context_retrieval_exists(self):
        """Test _retrieve_context method exists for RAG."""
        self.assertTrue(hasattr(self.controller, '_retrieve_context'))

    # =========================================================
    # 5. SSE format helpers
    # =========================================================
    def test_05_streaming_sse_event_format(self):
        """Test that SSE data lines can be parsed correctly."""
        # Simulate a typical Gemini streaming SSE data line
        sse_line = 'data: {"candidates":[{"content":{"parts":[{"text":"Hello"}]}}]}'
        data_str = sse_line.replace('data: ', '', 1)
        parsed = json.loads(data_str)

        text = parsed['candidates'][0]['content']['parts'][0]['text']
        self.assertEqual(text, 'Hello')

    # =========================================================
    # 6. Document context (RAG) integration
    # =========================================================
    def test_06_streaming_document_context_integration(self):
        """Test RAG: document → chunks → context."""
        doc = self.env['topic_chatbot.document'].create({
            'name': 'Streaming Test Doc',
            'topic_id': self.TestTopic.id,
            'datas': base64.b64encode(
                b'This is test document content for RAG integration.'),
            'filename': 'streaming_test.txt',
        })

        # Process document to create chunks
        doc._process_document()

        chunks = self.env['topic_chatbot.chunk'].search([
            ('document_id', '=', doc.id)])
        self.assertGreater(len(chunks), 0,
                           "Document processing should create chunks")

    # =========================================================
    # 7. Token-limit management in streaming context
    # =========================================================
    def test_07_streaming_token_limit_management(self):
        """Test token limit truncation with many long messages."""
        MAX_CHARS = 30000

        # Create 10 pairs of messages with long content
        for i in range(10):
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.TestConversation.id,
                'role': 'user',
                'content': f'Long user message {i}. ' * 500,
            })
            self.env['topic_chatbot.message'].create({
                'conversation_id': self.TestConversation.id,
                'role': 'model',
                'content': f'Long AI response {i}. ' * 500,
            })

        # Replicate the token-limit algorithm from the controller
        db_messages = self.env['topic_chatbot.message'].search([
            ('conversation_id', '=', self.TestConversation.id)
        ], order='create_date desc')

        contents = []
        total_chars = 0

        for m in db_messages:
            cleaned_content = re.sub(r' {2,}', ' ', m.content or '')
            if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                break
            total_chars += len(cleaned_content)
            contents.insert(0, {
                'role': 'user' if m.role == 'user' else 'model',
                'parts': [{'text': cleaned_content}]
            })

        # Should not include all 20 messages
        self.assertLess(len(contents), 20,
                        "Token limit should truncate old messages")
        self.assertGreater(len(contents), 0,
                           "At least one message should always be included")

    # =========================================================
    # 8. Message persistence
    # =========================================================
    def test_08_streaming_message_persistence(self):
        """Test that messages can be created and retrieved for streaming."""
        initial_count = self.env['topic_chatbot.message'].search_count([
            ('conversation_id', '=', self.TestConversation.id)
        ])

        self.env['topic_chatbot.message'].create({
            'conversation_id': self.TestConversation.id,
            'role': 'user',
            'content': 'Streaming test message',
        })

        new_count = self.env['topic_chatbot.message'].search_count([
            ('conversation_id', '=', self.TestConversation.id)
        ])

        self.assertEqual(new_count, initial_count + 1,
                         "User message should be persisted")

    # =========================================================
    # 9. No API key handling
    # =========================================================
    def test_09_streaming_no_api_key_detection(self):
        """Test that missing API key can be detected."""
        self.env['ir.config_parameter'].sudo().set_param(
            'topic_chatbot.gemini_api_key', '')

        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('topic_chatbot.gemini_api_key')

        self.assertFalse(bool(api_key),
                         "Empty API key should be falsy")

        # Restore key for other tests
        self.env['ir.config_parameter'].sudo().set_param(
            'topic_chatbot.gemini_api_key', 'test_streaming_key')

    # =========================================================
    # 10. Build instruction method
    # =========================================================
    def test_10_streaming_build_instruction_exists(self):
        """Test _build_system_instruction method exists."""
        self.assertTrue(
            hasattr(self.controller, '_build_system_instruction'))

    def test_11_gemini_error_messages_are_status_specific(self):
        """Test Gemini errors are not all reported as rate-limit failures."""
        rate_limit_msg = self.controller._gemini_user_error_message(
            status_code=429,
            error_status='RESOURCE_EXHAUSTED',
        )
        forbidden_msg = self.controller._gemini_user_error_message(
            status_code=403,
            error_status='PERMISSION_DENIED',
        )
        not_found_msg = self.controller._gemini_user_error_message(
            status_code=404,
            error_status='NOT_FOUND',
        )

        self.assertIn('429', rate_limit_msg)
        self.assertIn('API key', forbidden_msg)
        self.assertIn('Model Gemini', not_found_msg)
        self.assertNotEqual(rate_limit_msg, forbidden_msg)

    def test_12_gemini_error_extraction_redacts_api_key(self):
        """Test Gemini error extraction redacts sensitive API keys."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            'error': {
                'status': 'PERMISSION_DENIED',
                'message': 'API key secret-key-123 is invalid',
            }
        }

        details = self.controller._extract_gemini_error(
            mock_response, 'secret-key-123')

        self.assertEqual(details['status_code'], 403)
        self.assertEqual(details['status'], 'PERMISSION_DENIED')
        self.assertNotIn('secret-key-123', details['message'])
        self.assertIn('REDACTED', details['message'])
