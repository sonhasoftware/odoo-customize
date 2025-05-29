from odoo import fields, models

class DistributionChannel(models.Model):
    _name = 'distribution.channel'

    code = fields.Char("Mã")
    name = fields.Char("Tên")
    x_note = fields.Char("Ghi chú")