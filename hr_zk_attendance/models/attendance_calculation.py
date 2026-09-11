from odoo import models, fields, api

class AttendanceCalculation(models.Model):
    _name = 'attendance.calculation'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", store=True)
    date = fields.Date(string="Ngày", store=True)
    cal = fields.Boolean(string="Tính toán", store=True)
