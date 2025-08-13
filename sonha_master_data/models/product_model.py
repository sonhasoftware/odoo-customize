from odoo import api, fields, models


class ProductModel(models.Model):
    _name = 'product.model'

    name = fields.Char("Model")
    note = fields.Char("Ý nghĩa")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")

