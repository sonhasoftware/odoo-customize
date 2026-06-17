# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class DiscussChannelMember(models.Model):
    _inherit = 'discuss.channel.member'

    ai_agent_id = fields.Many2one(
        "ai.agent",
        compute="_compute_ai_agent_id",
        inverse="_inverse_ai_agent_id",
        compute_sudo=True,
    )

    @api.depends("livechat_member_history_ids.ai_agent_id")
    def _compute_ai_agent_id(self):
        for member in self:
            member.ai_agent_id = member.livechat_member_history_ids.ai_agent_id

    def _inverse_ai_agent_id(self):
        # sudo - im_livechat.channel.member: creating/updating history following
        # "ai_agent_id" modification is acceptable.
        self.sudo()._create_or_update_history(
            {member: {"ai_agent_id": member.ai_agent_id.id} for member in self}
        )

    def _get_excluded_rtc_members_partner_ids(self):
        excluded_partner_ids = super()._get_excluded_rtc_members_partner_ids()
        return excluded_partner_ids + self.channel_id.livechat_channel_id.rule_ids.ai_agent_id.partner_id.ids
