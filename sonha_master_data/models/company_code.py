from odoo import models, fields, api


class CompanyCode(models.Model):
    _name = 'company.code'
    _rec_name = 'code'

    company_id = fields.Many2one('res.company', string="Công ty")
    code = fields.Char("Mã công ty")