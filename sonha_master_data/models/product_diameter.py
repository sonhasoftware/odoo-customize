from odoo import api, fields, models


class ProductDiameter(models.Model):
    _name = 'product.diameter'

    name = fields.Char("Đường kính")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm/Công đoạn")
    note = fields.Char("Ý nghĩa")