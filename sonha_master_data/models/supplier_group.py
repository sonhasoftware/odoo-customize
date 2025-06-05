from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SupplierGroup(models.Model):
    _name = 'supplier.group'

    name = fields.Char("Tên nhóm nhà cc")
    code = fields.Char("Mã SAP")