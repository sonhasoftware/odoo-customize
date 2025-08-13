from odoo import api, fields, models


class ProductColor(models.Model):
    _name = 'product.color'

    name = fields.Char("Màu sắc")
    note = fields.Char("Ý nghĩa")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")