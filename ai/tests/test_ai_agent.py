# Part of Odoo. See LICENSE file for full copyright and licensing details.
from unittest.mock import patch

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAIAgent(TransactionCase):

    def test_close_chat_only_works_with_ai_channel(self):
        partner = self.env["res.partner"].create({
            "name": "Odoo AI"
        })

        agent = self.env["ai.agent"].create({
            "name": "Odoo AI",
            "partner_id": partner.id

        })
        ai_chat_channel = agent._get_or_create_ai_chat()
        regular_channel = self.env["discuss.channel"].create({
            "channel_member_ids": [
                Command.create(
                    {
                        "partner_id": self.env.user.partner_id.id,
                    }
                ),
            ],
            "channel_type": "chat",
            "name": "Non AI chat"
        })

        agent.close_chat(ai_chat_channel.id)
        agent.close_chat(regular_channel.id)
        self.assertFalse(ai_chat_channel.exists(), "Channel of type 'ai_chat' should be deleted when closed.")
        self.assertTrue(regular_channel.exists(), "Only channels in ['ai_chat', 'ai_composer'] should be deleted on close.")

    def test_generate_response_no_duplicate_user_prompt(self):
        """Test that user prompts are not duplicated when calling _generate_response"""
        agent = self.env["ai.agent"].create({
            "name": "Test AI Agent",
            "llm_model": "gpt-4",
        })
        channel = agent._get_or_create_ai_chat()

        # First 2 messages to simulate first question and response
        channel.message_post(
            body="first question",
            author_id=self.env.user.partner_id.id,
            message_type='comment',
        )
        channel.message_post(
            body="Sure, I'm here to help. What's your first question?",
            author_id=agent.partner_id.id,
            message_type='comment',
        )

        # Post a new message and followed by an explicit generate response call.
        # In the generate response, we check that the user prompt is not duplicated.
        channel.message_post(
            body="second question",
            author_id=self.env.user.partner_id.id,
            message_type='comment',
        )
        with patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request') as mock_request, \
             patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token') as mock_token:
            mock_token.return_value = 'test-api-key'
            mock_request.return_value = {
                'choices': [{
                    'message': {
                        'role': 'assistant',
                        'content': 'Response to second question',
                    },
                }],
            }

            agent._generate_response(prompt="second question")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            body = call_args[0][3]
            messages = body['input']

            user_messages = [msg for msg in messages if msg.get('role') == 'user']
            second_question_count = sum(1 for msg in user_messages if msg.get('content') == 'second question')

            self.assertEqual(second_question_count, 1, "User prompt 'second question' should appear only once in messages")
