from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpContractStateLog(models.Model):
    _name = 'exp.contract.state.log'
    _order = 'change_date desc'

    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    from_state_id = fields.Many2one('exp.contract.state', string="Từ trạng thái", store=True)
    to_state_id = fields.Many2one('exp.contract.state', string="Đến trạng thái", store=True)
    change_by = fields.Many2one('res.users', string="User thực hiện", required=True, store=True)
    change_date = fields.Datetime(string="Ngày thực hiện", default=fields.Datetime.now, required=True, store=True)
    note = fields.Text(string="Ghi chú", store=True)
