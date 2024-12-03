from odoo import models, fields, api


class MasterDataAttendance(models.Model):
    _name = 'master.data.attendance'
    _description = 'Master Data Attendance'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", compute="fill_department")
    attendance_time = fields.Datetime(string='Thời gian', required=True)

    @api.depends('employee_id')
    def fill_department(self):
        for r in self:
            r.department_id = r.employee.department_id.id if r.employee.department_id.id else None
