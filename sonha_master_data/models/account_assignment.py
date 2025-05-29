from odoo import fields, models


class AccountAssignment(models.Model):
    _name = 'account.assignment'

    code = fields.Char("Mã")
    name = fields.Char("Tên")
