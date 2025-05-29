from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CustomerGroup(models.Model):
    _name = 'customer.group'
    _rec_name = 'customer_group_name'

    customer_group_code = fields.Char("Mã nhóm khách hàng")
    customer_group_name = fields.Char("Tên nhóm khách hàng")