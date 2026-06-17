# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import users

from .common import AICommon


@tagged("post_install", "-at_install")
class TestAIMethods(HttpCase, AICommon):

    @patch("odoo.addons.ai.models.ai_agent.AIAgent._generate_response")
    @users('user')
    def test_ai_methods_call_without_error(self, mock_generate_response):
        """Test that all AI rpc methods can be called without errors"""
        # Sudo => creating an agent requires creating a 'res.partner' to be used for chat channels.
        # This is only allowed for admins
        agent = self.env["ai.agent"].sudo().create({"name": "Test AI Agent"})
        channel = agent._get_or_create_ai_chat()
        mail_message = self.env["mail.message"].create(
            {
                "body": "<p>Test prompt</p>",
                "model": "discuss.channel",
                "res_id": channel.id,
            }
        )

        # Test generate_response method
        mock_generate_response.return_value = ["Mocked response"]
        self.authenticate(self.test_user.login, self.test_user.login)
        self.make_jsonrpc_request(
            "/ai/generate_response",
            {
                "mail_message_id": mail_message.id,

                "channel_id": channel.id
            }
        )
        self.assertTrue(mock_generate_response.called)

        # Test post_error_message method
        mock_generate_response.reset_mock()
        self.make_jsonrpc_request(
            "/ai/post_error_message",
            {
                "error_message": "error",
                "channel_id": channel.id
            }
        )
        self.assertTrue(mock_generate_response.called)

        # Test get_direct_response method
        mock_generate_response.reset_mock()
        result = agent.get_direct_response("Direct prompt")
        self.assertTrue(mock_generate_response.called)
        self.assertEqual(result, ["Mocked response"])

    def test_ai_agent_allow_duplicate(self):
        agent = self.env["ai.agent"].create({"name": "Test Agent"})
        agent_copy = agent.copy()
        self.assertEqual(agent_copy.name, "Test Agent (copy)")
