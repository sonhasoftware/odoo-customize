from odoo import api, fields, models

class LeaveReport(models.Model):
    _name = 'leave.report'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    date = fields.Date(string="Ngày")
    leave = fields.Float(string="Số phép sử dụng")
    begin_period = fields.Float(string="Đầu kỳ")
    total_leave_left = fields.Float(string="Số phép còn lại")

    def create(self, vals):
        list_record = super(LeaveReport, self).create(vals)
        for record in list_record:
            used_leave = self.env['leave.report'].sudo().search([('employee_id', '=', record.employee_id.id)])
            total_used_leave = sum(used_leave.mapped('leave'))
            if record.begin_period > 0:
                record.total_leave_left = record.begin_period - total_used_leave
            else:
                record.total_leave_left = 0
        return list_record
