from odoo import models, fields, api


class MDApproveRole(models.Model):
    _name = 'md.approve.role'
    _rec_name = 'role'

    role = fields.Char("Vai trò")
    approve_employee = fields.Many2one('hr.employee', string="Người duyệt")