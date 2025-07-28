from odoo import api, fields, models


class ConfigBranch(models.Model):
    _name = 'config.branch'

    name = fields.Char("Tên chi nhánh")