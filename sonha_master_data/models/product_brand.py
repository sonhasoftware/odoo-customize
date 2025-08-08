from odoo import api, fields, models


class ProductBrand(models.Model):
    _name = 'product.brand'

    name = fields.Char("Nhãn hiệu/Chủng loại")
    # material_type = fields.Many2many('x.material.type', string="Loại vật tư")
    short_name = fields.Char("Tên viết tắt")
    full_name = fields.Char("Tên đầy đủ")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")
