from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ConfigCompetencyEmployee(models.Model):
    _name = 'config.competency.employee'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên", domain="[('company_id', '=', company_id)]")
    company_id = fields.Many2one('res.company', string="Công ty")
