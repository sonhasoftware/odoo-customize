from odoo import models, fields, api


class WizardReturnCard(models.TransientModel):
    _name = 'wizard.return.card'

    receive_people = fields.Many2one('hr.employee', string="Người nhận thẻ", required=True)
    receive_time = fields.Date("Ngày trả thẻ", required=True)
    return_people = fields.Many2one('hr.employee', string="Người trả thẻ",
                                    domain="[('department_id', '=', department_id)]", required=True)

    parent_id = fields.Many2one('book.car', string="Parent ID")
    department_id = fields.Many2one('hr.department', string="Phòng ban")

    def action_confirm(self):
        self.parent_id.write({
            'receive_people': self.receive_people.id,
            'return_people': self.return_people.id,
            'receive_time': self.receive_time,
            'status_issuing_card': 'done',
            'list_view_status': self.parent_id.list_view_status + " → Hoàn thành",
        })
        return {'type': 'ir.actions.act_window_close'}

