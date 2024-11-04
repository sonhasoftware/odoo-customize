from odoo import models, fields


class MasterDataAttendance(models.Model):
    _name = 'master.data.attendance'
    _description = 'Master Data Attendance'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    attendance_time = fields.Datetime(string='Thời gian', required=True)
