from odoo import api, fields, models


class ConfigApproval(models.Model):
    _name = 'config.approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date DESC'

    step = fields.Integer("Số bước", tracking=True)
    name = fields.Char("Tên cấu hình", tracking=True)
    company_id = fields.Many2one('res.company', tracking=True)
    department_id = fields.Many2one('hr.department', tracking=True)

    step_status = fields.One2many('step.step', 'config_approval')


