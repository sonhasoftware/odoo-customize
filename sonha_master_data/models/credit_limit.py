from odoo import models, fields, api


class CreditLimit(models.Model):
    _name = 'credit.limit'

    credit_segment = fields.Many2one('limit.area', "Vùng hạn mức", required=True)
    credit_limit = fields.Float("Hạn mức tín dụng")
    valid_date = fields.Date("Có hiệu lực đến")

    declare_customer = fields.Many2one('declare.md.customer')
    md_customer = fields.Many2one('md.customer')
