from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ValuationClass(models.Model):
    _name = 'valuation.class'

    name = fields.Char("Lớp định giá", required=True)
    material_type = fields.Many2many('x.material.type', string="Loại vật tư")
    company_ids = fields.Many2many('res.company', string="Công ty")