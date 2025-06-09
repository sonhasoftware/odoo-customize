from odoo import models, fields, api, _


class TaxClassification(models.Model):
    _name = 'tax.classification'
    _rec_name = 'x_full_name'

    name = fields.Char(string="Tên", required=True)
    code = fields.Char(string="Mã", required=True)

    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'code')
    def get_full_name(self):
        for r in self:
            if r.code and r.name:
                r.x_full_name = f"{r.code} - {r.name}"
            else:
                r.x_full_name = ""

