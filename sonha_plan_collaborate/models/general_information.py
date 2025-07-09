from odoo import api, fields, models


class GeneralInformation(models.Model):
    _name = 'general.information'

    employee_id = fields.Many2one('hr.employee', "Họ tên")
    job_id = fields.Many2one(related='employee_id.job_id', string="Chức danh")
    department_id = fields.Many2one(related='employee_id.department_id', string="Phòng ban/Bộ phận")
    from_to = fields.Char("Địa chỉ nơi đến")
    from_date = fields.Date("Từ ngày")
    to_date = fields.Date("Đến ngày")
    purpose = fields.Char("Mục đích chuyến đi")
    organization = fields.Char("Tên phía mời/Tổ chức chuyến công tác")

    plan_id = fields.Many2one('plan.collaborate')

