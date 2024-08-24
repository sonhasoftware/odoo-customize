from odoo import models, fields  # type: ignore


class HrContractType(models.Model):
    _name = 'hr.contract.type'
    _descripton = 'Contract Type'

    #
    id = fields.Char(string="ID", required=True)
    name = fields.Char(string='Tên', required=True)
    country_id = fields.Many2one('res.country', string='Country')
    description = fields.Char(string='Mô tả')