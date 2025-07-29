from odoo import api, fields, models


class ConfigApproval(models.Model):
    _name = 'config.approval'

    step = fields.Integer("Số bước")
    name = fields.Char("Tên cấu hình")
    company_id = fields.Many2one('res.company')
    department_id = fields.Many2one('hr.department')

    step_status = fields.One2many('step.step', 'config_approval')


