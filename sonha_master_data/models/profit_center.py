from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProfitCenter(models.Model):
    _name = 'profit.center'

    name = fields.Char("Mã", required=True)
    profit_center_name = fields.Char("Tên trung tâm doanh thu", required=True)
    sonha_plant = fields.Many2one('sonha.plant', string="Plant")

