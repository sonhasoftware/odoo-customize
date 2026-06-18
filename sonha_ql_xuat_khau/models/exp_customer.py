from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpTaskReminder(models.Model):
    _name = 'exp.customer'

    name = fields.Char(string="Tên khách hàng", store=True)
    address = fields.Char(string="Địa chỉ", store=True)
    code = fields.Char(string="Mã khách hàng", store=True)
    email = fields.Char(string="Email", store=True)
    phone = fields.Char(string="Số điện thoại", store=True)