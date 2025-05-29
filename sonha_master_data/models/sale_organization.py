from odoo import fields, models

class SaleOrganization(models.Model):
    _name = 'sale.organization'

    name = fields.Char("Tên")
    x_company = fields.Char("Công ty")
    x_note = fields.Char("Ghi chú")
    code = fields.Char('Mã')

