from odoo import models, fields, api

class ProductSize(models.Model):
    _name = 'product.size'

    name = fields.Char("Kích thước")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    note = fields.Char("Ý nghĩa")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm/Công đoạn")