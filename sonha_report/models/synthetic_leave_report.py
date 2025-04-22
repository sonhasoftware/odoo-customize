from odoo import api, fields, models

class SyntheticLeaveReport(models.Model):
    _name = 'synthetic.leave.report'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    from_date = fields.Date(string="Từ ngày")
    to_date = fields.Date(string="Đến ngày")
    begin_period = fields.Float(string="Đầu kỳ")
    leave = fields.Float(string="Số phép sử dụng")
    total_leave_left = fields.Float(string="Số phép còn lại")


