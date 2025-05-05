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
        if self.parent_id.booking_employee_id.work_email:
            request_template = self.env.ref('sonha_book_car.template_mail_accept_to_creator')
            request_template.send_mail(self.parent_id.id, force_send=True)
        return {'type': 'ir.actions.act_window_close'}

