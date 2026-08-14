from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpMailLog(models.Model):
    _name = 'exp.mail.log'
    _order = 'send_date desc'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    send_date = fields.Datetime(string="Ngày gửi", store=True)
    note = fields.Text(string="Ghi chú", store=True)
