from odoo import models, fields, api


class WizardExistCar(models.TransientModel):
    _name = 'wizard.exist.car'

    driver = fields.Many2one('hr.employee', string="Lái xe", domain="[('company_id', '=', company_id)]")
    driver_phone = fields.Char("Số điện thoại lái xe", required=True)
    license_plate = fields.Char("Biển số xe", required=True)
    rent_company = fields.Char("Đơn vị")
    type = fields.Selection([('non_rent', "Xe đơn vị"),
                             ('rent_car', "Thuê xe DVTV")],
                            default='non_rent', required=True, string="Loại")

    company_id = fields.Many2one('res.company', string="Công ty")
    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        edit_infor = 0
        new_infor = 0
        if (self.parent_id.driver and self.parent_id.driver.id != self.driver.id) or (
                self.parent_id.driver_phone and self.parent_id.driver_phone != self.driver_phone) or (
                self.parent_id.license_plate and self.parent_id.license_plate != self.license_plate) or (
                self.parent_id.rent_company and self.parent_id.rent_company != self.rent_company) or (
                self.parent_id.is_rent and self.type == 'non_rent') or (
                not self.parent_id.is_rent and self.type == 'rent_car'):
            edit_infor = 1
        if not self.parent_id.driver and not self.parent_id.driver_phone and not self.parent_id.license_plate and not self.parent_id.rent_company:
            new_infor = 1
        parent_status = "Nháp → Chờ duyệt → Đã duyệt"
        status = " → Cấp xe"
        if self.type == 'rent_car':
            status = " → Cấp xe(Thuê)"
        if new_infor == 1 or (edit_infor == 1 and (self.parent_id.is_rent and self.type == 'non_rent') or (
                                                        not self.parent_id.is_rent and self.type == 'rent_car')):
            new_status = parent_status + status
        else:
            new_status = parent_status
        self.parent_id.write({
            'driver': self.driver.id if self.type == 'non_rent' else None,
            'driver_phone': self.driver_phone,
            'license_plate': self.license_plate,
            'status_exist_car': 'exist',
            'type': 'exist_car',
            'list_view_status': new_status,
            'rent_company': self.rent_company if self.type == 'rent_car' else "",
            'is_rent': True if self.type == 'rent_car' else False,
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
