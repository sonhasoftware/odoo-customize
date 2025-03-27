from odoo import api, fields, models

class ProductType(models.Model):
    _name = 'product.type'

    _rec_name = 'product_type_name'
    product_type_code = fields.Char(string="Mã loại sản phẩm")
    product_type_name = fields.CHar(string="Tên loại sản phẩm")
    company_id = fields.Many2one("res.company", string="Công ty")