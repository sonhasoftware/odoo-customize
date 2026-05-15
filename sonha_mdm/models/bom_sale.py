from odoo import fields, models


class BomSale(models.Model):
    _name = 'bom.sale'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Char("Tên", store=True)
