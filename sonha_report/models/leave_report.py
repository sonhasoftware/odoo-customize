from odoo import api, fields, models

class LeaveReport(models.Model):
    _name = 'leave.report'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    date = fields.Date(string="Ngày")
    leave = fields.Float(string="Số phép sử dụng")
    begin_period = fields.Float(string="Số phép khả dụng")
    total_leave_left = fields.Float(string="Số phép còn lại")

