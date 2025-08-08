from odoo import models, fields, api

class ProductThickness(models.Model):
    _name = 'product.thickness'

    name = fields.Char("Độ dày")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    note = fields.Char("Ý nghĩa")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm/Công đoạn")
