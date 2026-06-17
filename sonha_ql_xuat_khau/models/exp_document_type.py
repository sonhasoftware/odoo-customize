from odoo import models, fields, api


class ExpDocumentType(models.Model):
    _name = 'exp.document.type'

    code = fields.Char(string="Mã chứng từ", required=True, store=True)
    name = fields.Char(string="Tên chứng từ", required=True, store=True)
    active = fields.Boolean(string="Có được sử dụng không", store=True)
