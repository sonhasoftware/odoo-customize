from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProfitCenter(models.Model):
    _name = 'profit.center'

    name = fields.Char("Mã")
    profit_center_name = fields.Char("Tên trung tâm doanh thu")
    plant = fields.Many2one('stock.warehouse', string="Plant")

