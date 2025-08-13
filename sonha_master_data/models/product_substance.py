from odoo import api, fields, models


class ProductSubstance(models.Model):
    _name = 'product.substance'

    name = fields.Char("Chất liệu")
    short_name = fields.Char("Tên viết tắt")
    full_name = fields.Char("Tên đầy đủ")
    note = fields.Char("Ý nghĩa")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")