from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CustomerType(models.Model):
    _name = 'customer.type'
    _rec_name = 'customer_type_name'

    customer_type_code = fields.Char("Mã loại khách hàng")
    customer_type_name = fields.Char("Tên loại khách hàng")