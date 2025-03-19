from odoo import api, fields, models

class SonHaProduct(models.Model):
    _name = 'sonha.product'
    _rec_name = 'product_code'

    product_code = fields.Char(string="Mã sản phẩm")
    product_name = fields.Text(string="Tên sản phẩm")
    product_type = fields.Many2one('product.type', string="Loại sản phẩm")
    unit = fields.Char(string="ĐVT")
    note = fields.Text(string="Ghi chú")