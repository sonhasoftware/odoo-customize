from odoo import models, fields, api


class WizardNotIssuingCard(models.TransientModel):
    _name = 'wizard.not.issuing.card'

    reason = fields.Text("Lý do")

    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        self.parent_id.write({
            'reason': self.reason,
            'status': 'cancel',
            'type': 'cancel',
            'list_view_status': self.parent_id.list_view_status + " → Hủy"
        })
        return {'type': 'ir.actions.act_window_close'}