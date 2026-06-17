# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.ai_crm.tests.test_ai_crm_tools import TestAiCrmTools
from odoo.tests import tagged
from odoo.tests.common import users


@tagged('post_install', '-at_install')
class TestAiCrmLivechatTools(TestAiCrmTools):

    @users('public_user')
    def test_create_lead_tool_from_livechat(self):
        # check that the lead is created with the origin_channel_id
        tool = self.env.ref('ai_crm.ir_actions_server_ai_create_lead').sudo()
        livechat_channel = self.env['discuss.channel'].sudo().create({'name': 'create lead ai livechat', 'channel_type': 'livechat',
            'livechat_operator_id': self.agent.partner_id.id, 'ai_agent_id': self.agent.id})
        tool.with_context({'discuss_channel': livechat_channel})._ai_tool_run(None, {
            'name': 'AI Lead',
            'contact_name': 'Frank',
            'description': '<p onclick="alert(1)">AI created lead</p>',
            'email': 'mail@example.come',
            'phone': '+32123456789',
            'priority': '1',
            'team_id': self.team_ids[1].id,
            'tag_ids': self.tag_ids.ids,
        })
        lead = self.env['crm.lead'].sudo().search([], order='id desc', limit=1)
        self.assertEqual(1, self.agent.created_leads_count)
        self.assertEqual(livechat_channel, lead.origin_channel_id)
