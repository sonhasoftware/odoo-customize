from odoo import models, fields, api


class ShippingCondition(models.Model):
    _name = 'shipping.condition'
    _rec_name = 'description'

    code = fields.Char("Mã")
    description = fields.Char("Diễn giải")