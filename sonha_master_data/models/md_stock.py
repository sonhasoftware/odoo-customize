from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDStock(models.Model):
    _name = 'md.stock'

    name = fields.Char("Tên kho")
    stock_code = fields.Char("Mã kho")
    company_id = fields.Many2one('res.company', string="Đơn vị")