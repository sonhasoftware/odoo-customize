# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import Command
from odoo.tests import HttpCase, users

from .common import AICommon


class TestDiscussChannel(HttpCase, AICommon):

    def test_create_ai_chat(self):
        agent = self.env["ai.agent"].create({"name": "Odoo AI"})
        channel = agent._get_or_create_ai_chat()

        self.assertTrue(channel)
        self.assertTrue(channel.is_member, "Current user should be member of the created channel")
        self.assertEqual("ai_chat", channel.channel_type, "AI channel should be of 'ai_chat' type")
        self.assertEqual(agent.partner_id.name, channel.name, "Channel should be named after the agent's name")
        self.assertEqual(agent, channel.sudo().ai_agent_id, "ai_agent_id should be set on the newly created ai_chat channel")

    def test_create_ai_chat_retrieves_existing_channel(self):
        agent = self.env["ai.agent"].create({"name": "Odoo AI"})
        channel = agent._get_or_create_ai_chat()
        duplicate_channel = agent._get_or_create_ai_chat()

        self.assertEqual(channel, duplicate_channel, "ai_chat channel shouldn't be duplicated when created with the same agent.")

    @users('user')
    def test_close_ai_chat_deletes_channel(self):
        # Sudo => creating an agent requires creating a 'res.partner' to be used for chat channels.
        # This is only allowed for admins
        agent = self.env["ai.agent"].sudo().create({"name": "Odoo AI"})
        channel = agent._get_or_create_ai_chat()

        self.authenticate(self.test_user.login, self.test_user.login)
        self.make_jsonrpc_request("/ai/close_ai_chat", {"channel_id": channel.id})

        self.assertFalse(channel.exists(), "Channel of type 'ai_chat' should be deleted when closed.")

    @users('user')
    def test_close_ai_chat_only_deletes_channel_with_proper_types(self):
        # Sudo => creating an agent requires creating a 'res.partner' to be used for chat channels.
        # This is only allowed for admins
        agent = self.env["ai.agent"].sudo().create({"name": "Odoo AI"})
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

        self.authenticate(self.test_user.login, self.test_user.login)
        self.make_jsonrpc_request("/ai/close_ai_chat", {"channel_id": ai_chat_channel.id})
        self.make_jsonrpc_request("/ai/close_ai_chat", {"channel_id": regular_channel.id})

        self.assertFalse(ai_chat_channel.exists(), "Channel of type 'ai_chat' should be deleted when closed.")
        self.assertTrue(regular_channel.exists(), "Only channels in ['ai_chat', 'ai_composer'] should be deleted on close.")
