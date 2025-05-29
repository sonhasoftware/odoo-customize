from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AlternativeUom(models.Model):
    _name = 'alternative.uom'

    product_code_id = fields.Many2one('md.product', string="Mã vật tư")
    alternative_unit = fields.Many2one('uom.uom', string="Đơn vị thay thế")
    denominator = fields.Float("Mẫu số")
    numerator = fields.Float("Tử số")
    unit_measure = fields.Boolean("Đơn vị tính thứ 2")
    char_name = fields.Many2one('uom.characteristic', string="Tên thuộc tính")




