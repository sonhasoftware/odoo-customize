from odoo import api, fields, models


class ProductNameRule(models.Model):
    _name = 'product.name.rule'

    product_line = fields.Many2one('product.line', string="Dòng sản phẩm")
    product_stage = fields.Many2one('product.stage', string="Công đoạn/Sản phẩm")
    brand = fields.Boolean("Nhãn hiệu/Chủng loại")
    model = fields.Boolean("Model")
    style = fields.Boolean("Kiểu dáng")
    capacity = fields.Boolean("Dung tích")
    power = fields.Boolean("Công suất")
    substance = fields.Boolean("Chất liệu")
    surface = fields.Boolean("Kiểu bề mặt/Độ bóng")
    diameter = fields.Boolean("Đường kính")
    thickness = fields.Boolean("Độ dày")
    size = fields.Boolean("Chiều dài, rộng, cao")
    chemical = fields.Boolean("TP hóa học")
    color = fields.Boolean("Màu sắc")
    other = fields.Boolean("Khác")