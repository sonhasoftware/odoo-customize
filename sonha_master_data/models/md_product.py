from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDProduct(models.Model):
    _name = 'md.product'

    product_code = fields.Char("Mã vật tư")
    product_type = fields.Many2one('x.material.type', string="Loại vật tư")
    product_name = fields.Char("Tên vật tư", size=40)
    product_english_name = fields.Char("Tên vật tư tiếng anh", size=40)
    product_long_name = fields.Char("Tên đầy đủ", size=128)
    basic_data = fields.One2many('basic.mat.data', 'md_product_id', string="Thông tin cơ bản")
    alternative_uom = fields.One2many('alternative.uom', 'md_product_id', string="Đơn vị thay thế")
    plant_data = fields.One2many('plant.data', 'md_product_id', string="Thông tin plant")
    sale_data = fields.One2many('sales.data', 'md_product_id', string="Thông tin bán hàng")
    declare_product = fields.Many2one('declare.md.product')




