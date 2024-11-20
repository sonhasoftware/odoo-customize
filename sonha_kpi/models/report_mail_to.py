from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ReportMailTo(models.Model):
    _name = 'report.mail.to'

    module = fields.Many2one('ir.module.module', string="Module")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    receive_emp = fields.Many2one('hr.employee', string="Người nhận")
    cc_to = fields.Many2many('hr.employee', string="cc tới", readonly=False)

