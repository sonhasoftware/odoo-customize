from odoo import api, fields, models


class ProductChemical(models.Model):
    _name = 'product.chemical'

    name = fields.Char("TP hóa học")
    note = fields.Char("Ý nghĩa")