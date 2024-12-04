from odoo import api, fields, models
from datetime import datetime, time, timedelta


class DistributeShift(models.Model):
    _name = 'distribute.shift'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", compute="fill_department")
    date = fields.Date(string="Ngày")
    shift = fields.Many2one('config.shift', string="Ca làm việc")

    @api.depends('employee_id')
    def fill_department(self):
        for r in self:
            r.department_id = r.employee_id.department_id.id if r.employee_id.department_id.id else None

