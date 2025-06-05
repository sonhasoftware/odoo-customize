from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class OverheadGroup(models.Model):
    _name = 'overhead.group'
    _rec_name='x_full_name'

    name = fields.Char("Nhóm chi phí chung", required=True)
    description = fields.Char("Diễn giải", required=True)
    company_id = fields.Many2one('res.company', string="Công ty")
    plant = fields.Many2one('stock.warehouse', string="Plant")

    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'description')
    def get_full_name(self):
        for r in self:
            if r.name and r.description:
                r.x_full_name = f"{r.name} - {r.description}"
            else:
                r.x_full_name = ""

