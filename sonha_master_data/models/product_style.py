from odoo import api, fields, models


class ProductStyle(models.Model):
    _name = 'product.style'

    name = fields.Char("Kiểu dáng")
    short_name = fields.Char("Tên viết tắt")
    full_name = fields.Char("Tên đầy đủ")
    note = fields.Char("Ý nghĩa")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")