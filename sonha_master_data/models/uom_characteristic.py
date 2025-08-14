from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class UomCharacteristic(models.Model):
    _name = 'uom.characteristic'
    _rec_name = 'characteristic'

    uom = fields.Many2one('sonha.uom', string="Đơn vị", required=True)
    characteristic = fields.Char("Đặc điểm")

