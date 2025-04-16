from odoo import models, fields, api


class WizardExistCar(models.TransientModel):
    _name = 'wizard.exist.car'

    driver = fields.Many2one('hr.employee', string="Lái xe", required=True)
    driver_phone = fields.Char("Số điện thoại lái xe", required=True)
    license_plate = fields.Char("Biển số xe", required=True)

    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        self.parent_id.write({
            'driver': self.driver.id,
            'driver_phone': self.driver_phone,
            'license_plate': self.license_plate,
            'status_exist_car': 'exist',
            'type': 'exist_car',
            'list_view_status': self.parent_id.list_view_status + " → Cấp xe",
        })
        return {'type': 'ir.actions.act_window_close'}