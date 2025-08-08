from odoo import api, fields, models


class ProductSurface(models.Model):
    _name = 'product.surface'

    name = fields.Char("Kiểu bề mặt")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    note = fields.Char("Ý nghĩa")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm/Công đoạn")
