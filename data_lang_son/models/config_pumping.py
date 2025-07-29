from odoo import api, fields, models


class ConfigPumping(models.Model):
    _name = 'config.pumping'

    name = fields.Char("Tên Tra bơm", required=True)
    branch_id = fields.Many2one('config.branch', string="Tên chi nhánh", required=True)
    user_id = fields.Many2one('res.users', string="Người dùng")
    date = fields.Integer("Ngày")
