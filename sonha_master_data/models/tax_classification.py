from odoo import models, fields, api, _


class TaxClassification(models.Model):
    _name = 'tax.classification'

    name = fields.Char(string="Tên")
    code = fields.Char(string="Mã")