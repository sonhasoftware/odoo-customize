from odoo import api, fields, models


class ProductLine(models.Model):
    _name = 'product.line'

    name = fields.Char("Dòng sản phẩm")
    material_type = fields.Many2many('x.material.type', string="Loại sản phẩm")
    full_name = fields.Char("Tên đầy đủ")
    short_name = fields.Char("Tên viết tắt")
    is_main_material = fields.Boolean("Nguyên vật liệu chính")