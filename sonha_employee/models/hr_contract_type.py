from odoo import models, fields  # type: ignore


class HrContractType(models.Model):
    _name = 'hr.contract.type'
    _descripton = 'Contract Type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    #
    id = fields.Char(string="ID", required=True, tracking=True)
    name = fields.Char(string='Tên', required=True, tracking=True)
    country_id = fields.Many2one('res.country', string='Country')
    description = fields.Char(string='Mô tả', tracking=True)
    file = fields.Binary("File")
