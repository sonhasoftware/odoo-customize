from odoo import api, fields, models


class ErrorCode(models.Model):
    _name = 'error.code'
    _rec_name = 'error_code'

    error_code = fields.Char(string="Mã lỗi")
    error_name = fields.Text(string="Tên lỗi")
    error_group_id = fields.Many2one("error.group", string="Nhóm lỗi")
    product_type_id = fields.Many2one("product.type", string="Loại sản phẩm")
    # company_id = fields.Many2one("res.company", string="Công ty")
