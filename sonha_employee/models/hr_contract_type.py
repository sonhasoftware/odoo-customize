from odoo import models, fields  # type: ignore


class HrContractType(models.Model):
    _name = 'hr.contract.type'
    _description = 'Contract Type'

    #
    id = fields.Char(string="ID Loại hợp đồng", required=True)
    name = fields.Char(string='Tên Loại hợp đồng', required=True)
    country_id = fields.Many2one('res.country', string='Country')
    description = fields.Char(string='Mô tả')
    file = fields.Binary(string="File In hợp đồng")