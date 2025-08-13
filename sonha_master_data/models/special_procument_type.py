from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SpecialProcumentType(models.Model):
    _name = 'special.procument.type'

    name = fields.Char("Loại", required=True)
    procument_type_name = fields.Char("Tên loại hình thức cung ứng", required=True)
    sonha_plant = fields.Many2many('sonha.plant', string="Plant áp dụng")
