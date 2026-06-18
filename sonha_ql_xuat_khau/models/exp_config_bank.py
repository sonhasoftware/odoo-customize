from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpConfigBank(models.Model):
    _name = 'exp.config.bank'

    code = fields.Char(string="Swift Code", store=True)
    name = fields.Char(string="Tên ngân hàng", store=True)
    account_name = fields.Char(string="Tên tài khoản", store=True)
    account_no = fields.Char(string="Số tài khoản", store=True)
    address = fields.Char(string="Địa chỉ", store=True)


class ExpConfigCurrency(models.Model):
    _name = 'exp.config.currency'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Tên tiền tệ", store=True)
