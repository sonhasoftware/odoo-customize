from odoo import api, fields, models

class LeaveReport(models.Model):
    _name = 'leave.report'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    date = fields.Date(string="Ngày")
    leave = fields.Float(string="Số phép sử dụng")
    begin_period = fields.Float(string="Số phép khả dụng")
    total_leave_left = fields.Float(string="Số phép còn lại")

    def create(self, vals):
        list_record = super(LeaveReport, self).create(vals)
        for record in list_record:
            if record.begin_period > 0:
                record.total_leave_left = record.begin_period - record.leave
            else:
                record.total_leave_left = 0
        return list_record
