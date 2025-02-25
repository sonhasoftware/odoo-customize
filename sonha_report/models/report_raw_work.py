from odoo import api, fields, models


class ReportRawWork(models.Model):
    _name = 'report.raw.work'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)
    attendance_time = fields.Datetime(string='Thời gian', required=True)

