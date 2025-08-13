from odoo import models, fields, api


class BankCountry(models.Model):
    _name = 'bank.country'
    _rec_name = 'code'

    code = fields.Char("Mã quốc gia")
    name = fields.Char("Tên quốc gia")