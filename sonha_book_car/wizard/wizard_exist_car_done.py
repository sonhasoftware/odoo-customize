from odoo import models, fields, api


class WizardExistCarDone(models.TransientModel):
    _name = 'wizard.exist.car.done'

    driver = fields.Many2one('hr.employee', string="Lái xe", required=True)
    driver_phone = fields.Char("Số điện thoại lái xe", required=True)
    license_plate = fields.Char("Biển số xe", required=True)
    reality_start_date = fields.Date("Ngày khởi hành thực tế")
    reality_end_date = fields.Date("Ngày kết thúc thực tế")

    parent_id = fields.Many2one('book.car', string="Parent ID")

    def action_confirm(self):
        self.parent_id.write({
            'reality_start_date': self.reality_start_date,
            'reality_end_date': self.reality_end_date,
            'status_exist_car': 'done',
            'list_view_status': self.parent_id.list_view_status + " → Hoàn thành",
        })
        return {'type': 'ir.actions.act_window_close'}

