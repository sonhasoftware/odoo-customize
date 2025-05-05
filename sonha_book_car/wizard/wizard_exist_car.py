from odoo import models, fields, api


class WizardExistCar(models.TransientModel):
    _name = 'wizard.exist.car'

    driver = fields.Many2one('hr.employee', string="Lái xe", required=True)
    driver_phone = fields.Char("Số điện thoại lái xe", required=True)
    license_plate = fields.Char("Biển số xe", required=True)

    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        edit_infor = 1 if self.parent_id.driver and self.parent_id.driver.id != self.driver.id else 0
        new_infor = 1 if not self.parent_id.driver else 0
        self.parent_id.write({
            'driver': self.driver.id,
            'driver_phone': self.driver_phone,
            'license_plate': self.license_plate,
            'status_exist_car': 'exist',
            'type': 'exist_car',
            'list_view_status': self.parent_id.list_view_status + " → Cấp xe" if not self.parent_id.driver else self.parent_id.list_view_status,
        })
        if new_infor != 0:
            if self.parent_id.driver.work_email:
                request_template = self.env.ref('sonha_book_car.template_mail_accept_to_driver')
                request_template.send_mail(self.parent_id.id, force_send=True)
            if self.parent_id.booking_employee_id.work_email:
                request_template = self.env.ref('sonha_book_car.template_mail_accept_to_creator')
                request_template.send_mail(self.parent_id.id, force_send=True)
        if edit_infor != 0:
            if self.parent_id.booking_employee_id.work_email:
                request_template = self.env.ref('sonha_book_car.template_mail_edit_driver_infor')
                request_template.send_mail(self.parent_id.id, force_send=True)
            if self.parent_id.driver.work_email:
                request_template = self.env.ref('sonha_book_car.template_mail_accept_to_driver')
                request_template.send_mail(self.parent_id.id, force_send=True)
        return {'type': 'ir.actions.act_window_close'}