from unittest.mock import patch

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.tests import TransactionCase


class TestAiServerActions(TransactionCase):
    def _mock_llm_api_get_token(self):
        def _mock_get_api_token(self):
            return "dummy"
        return patch.object(LLMApiService, '_get_api_token', _mock_get_api_token)

    def test_ai_server_action(self):
        def _mocked_llm_api_request(cls, method, endpoint, headers, body):
            self.assertEqual(body['input'][1]['content'][0]['text'], "Write 1337")
            return {'output': [{'type': 'message', 'content': [{'text': '{"value": "1337"}'}]}]}

        partner = self.env["res.partner"].create({"name": "Partner"})
        field = self.env["ir.model.fields"]._get(partner._name, "name").id
        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "object_write",
                "name": "Test",
                "evaluation_type": "ai_computed",
                "ai_update_prompt": "Write 1337",
                "update_field_id": field,
            },
        )

        with patch.object(LLMApiService, '_request', _mocked_llm_api_request), \
            self._mock_llm_api_get_token():
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(partner.name, "1337")
