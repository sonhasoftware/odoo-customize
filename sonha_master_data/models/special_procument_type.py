from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SpecialProcumentType(models.Model):
    _name = 'special.procument.type'

    name = fields.Char("Loại")
    procument_type_name = fields.Char("Tên loại hình thức cung ứng")
    plant = fields.Many2many('stock.warehouse', string="Plant áp dụng")
