from odoo import models, fields, api


class ConfigApproveLine(models.Model):
    _name = 'config.approve.line'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    approve_people = fields.Many2one('hr.employee', string="Người duyệt")
    competency_employee = fields.Many2one('hr.employee', string="Nhân viên sử lý")