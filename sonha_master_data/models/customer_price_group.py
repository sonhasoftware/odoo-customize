from odoo import models, fields, api


class CustomerPriceGroup(models.Model):
    _name = 'customer.price.group'
    _rec_name = 'description'

    code = fields.Char("Mã")
    description = fields.Char("Diễn giải")

