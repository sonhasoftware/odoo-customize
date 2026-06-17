from odoo import models, fields


class ImLivechatChannelMemberHistory(models.Model):
    _inherit = "im_livechat.channel.member.history"

    ai_agent_id = fields.Many2one(
        "ai.agent", compute="_compute_member_fields", index="btree_not_null", store=True
    )

    def _compute_member_fields(self):
        super()._compute_member_fields()
        for history in self:
            history.ai_agent_id = history.ai_agent_id or history.member_id.ai_agent_id
