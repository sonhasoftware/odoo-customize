from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class UomCharacteristic(models.Model):
    _name = 'uom.characteristic'
    _rec_name = 'characteristic'

    unit_material = fields.Many2one('uom.uom', string="Đơn vị")
    characteristic = fields.Char("Đặc điểm")

