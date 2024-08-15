from odoo import api, fields, models
from datetime import datetime


class EmployeeAttendance(models.Model):
    _name = 'employee.attendance'
    _description = 'Employee Attendance'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    attendance_date = fields.Date(string='Attendance Date', required=True)
    check_in = fields.Datetime(string='Check In', required=True)
    check_out = fields.Datetime(string='Check Out', required=True)

    @api.model
    def create_attendance_records(self):
        master_attendance = self.env['master.data.attendance']
        records = master_attendance.read_group(
            [('attendance_time', '!=', False)],
            ['employee_id', 'attendance_time:min(attendance_time) as check_in', 'attendance_time:max(attendance_time) as check_out'],
            ['employee_id', 'attendance_date']
        )

        for record in records:
            self.create({
                'employee_id': record['employee_id'][0],
                'attendance_date': record['attendance_date'],
                'check_in': record['check_in'],
                'check_out': record['check_out'],
            })
