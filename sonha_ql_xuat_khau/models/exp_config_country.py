from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpConfigCountry(models.Model):
    _name = 'exp.config.country'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Tên quốc gia", store=True)


class ExpConfigTerm(models.Model):
    _name = 'exp.config.term'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Điều khoản thanh toán", store=True)


class ExpConfigPort(models.Model):
    _name = 'exp.config.port'

    code = fields.Char(string="Mã", store=True)
    name = fields.Char(string="Tên cảng", store=True)
    type = fields.Selection([('port_form', "Cảng bốc"),
                             ('port_to', "Cảng dỡ")], string="Loại cảng", store=True)
    country_id = fields.Many2one('exp.config.country', string="Quốc gia", store=True)
