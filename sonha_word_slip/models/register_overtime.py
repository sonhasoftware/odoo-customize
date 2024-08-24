from odoo import api, fields, models


class RegisterOvertime(models.Model):
    _name = 'register.overtime'

    employee_id = fields.Many2many('hr.employee', 'register_overtime_rel',
                                   'register_overtime', 'register_overtime_id',
                                   string="Tên nhân viên")
    shift = fields.Many2one('config.shift', string="Ca")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
    start_time = fields.Float("Thời gian bắt đầu")
    end_time = fields.Float("Thời gian kết thúc")
