from odoo import models, fields, api, _  # type: ignore


class HrContract(models.Model):
    _inherit = 'hr.contract'

    #
    contract_type_id = fields.Many2one('hr.contract.type', string="Loại hợp đồng", ondelete='cascade')