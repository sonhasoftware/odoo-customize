# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    @api.depends("state", "child_ids", "evaluation_type")
    def _compute_ai_tool_is_candidate(self):
        account_actions = self.filtered(lambda a: a.state == "documents_account_record_create")
        account_actions.ai_tool_is_candidate = True
        super(IrActionsServer, self - account_actions)._compute_ai_tool_is_candidate()
