from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpConfigData(models.Model):
    _name = 'exp.config.data'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Tên", store=True)
    data = fields.Char(string="Dữ liệu", store=True)
    note = fields.Char(string="Ghi chú", store=True)