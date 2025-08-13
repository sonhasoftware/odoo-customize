from odoo import models, fields, api


class OrderCurrency(models.Model):
    _name = 'order.currency'

    name = fields.Char("Tên")
    full_name = fields.Char("Tên đầy đủ")
    country = fields.Char("Khu vực")
