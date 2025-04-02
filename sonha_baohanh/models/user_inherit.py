from odoo import api, fields, models


class UserInherit(models.Model):
    _inherit = 'res.users'

    branch_ids = fields.Many2many('bh.branch', string="Chi nhánh")