from odoo import models, fields, api


class WizardReturnCard(models.TransientModel):
    _name = 'wizard.return.card'

    receive_people = fields.Many2one('hr.employee', string="Người nhận thẻ", required=True)
    receive_time = fields.Date("Ngày trả thẻ", required=True)

    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        self.parent_id.write({
            'receive_people': self.receive_people,
            'receive_time': self.receive_time,
            'status': 'done',
            'issuing_card': True,
        })
        return {'type': 'ir.actions.act_window_close'}