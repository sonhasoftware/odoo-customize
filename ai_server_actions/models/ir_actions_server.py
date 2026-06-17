# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    evaluation_type = fields.Selection(
        selection_add=[("ai_computed", "Update with AI")],
    )
    ai_update_prompt = fields.Html("AI Update Prompt", sanitize=True, sanitize_output_method="xml")
    update_field_name = fields.Char(related='update_field_id.name')
    update_field_relation = fields.Char(related="update_field_id.relation")
    update_field_type = fields.Selection(related='update_field_id.ttype')

    @api.constrains('evaluation_type', 'update_field_id', 'state')
    def _check_ai_evaluation_type(self):
        for action in self:
            if action.state == 'object_write' and action.evaluation_type == 'ai_computed' and not action.update_field_id.store:
                raise ValidationError(_("This field can not be computed with AI (not stored)."))

    def _run_action_object_write(self, eval_context=None):
        ai_actions = self.filtered(lambda a: a.evaluation_type == "ai_computed")
        if self - ai_actions:
            super(IrActionsServer, self - ai_actions)._run_action_object_write(eval_context)

        records = self._ai_get_records(eval_context)
        for action in ai_actions:
            field = action.update_field_id
            records._fill_ai_field(self.env[field.model]._fields.get(field.name), action.ai_update_prompt)
