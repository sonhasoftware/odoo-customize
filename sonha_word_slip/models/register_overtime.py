from odoo import api, fields, models


class RegisterOvertime(models.Model):
    _name = 'register.overtime'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
    start_time = fields.Float("Thời gian bắt đầu")
    end_time = fields.Float("Thời gian kết thúc")
