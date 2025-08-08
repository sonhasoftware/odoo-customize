from odoo import api, fields, models


class ProductStage(models.Model):
    _name = 'product.stage'

    name = fields.Char("Sản phẩm/Công đoạn")
    product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    full_name = fields.Char("Tên đầy đủ")
    short_name = fields.Char("Tên viết tắt")
    