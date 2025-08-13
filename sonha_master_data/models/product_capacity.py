from odoo import api, fields, models


class ProductCapacity(models.Model):
    _name = 'product.capacity'

    name = fields.Char("Dung tích")
    short_name = fields.Char("Tên viết tắt")
    full_name = fields.Char("Tên đầy đủ")
    # product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    # product_stage = fields.Many2one('product.stage', string="Sản phẩm")
    type = fields.Selection([('capacity', "Dung tích"), ('power', "Công suất")], string="Loại")