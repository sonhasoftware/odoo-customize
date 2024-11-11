from odoo import api, fields, models
from datetime import datetime, time, timedelta


class DistributeShift(models.Model):
    _name = 'distribute.shift'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    date = fields.Date(string="Ngày")
    shift = fields.Many2one('config.shift', string="Ca làm việc")

