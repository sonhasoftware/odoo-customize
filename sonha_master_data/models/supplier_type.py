from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SupplierType(models.Model):
    _name = 'supplier.type'

    name = fields.Char("Tên loại nhà cc")
    code = fields.Char("Mã SAP")