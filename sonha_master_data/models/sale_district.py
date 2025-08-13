from odoo import models, fields, api


class SaleDistrict(models.Model):
    _name = 'sale.district'
    _rec_name = 'display_name'

    code = fields.Char("Mã vùng kinh doanh")
    description = fields.Char("Diễn giải")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('code', 'description')
    def compute_display_name(self):
        for r in self:
            if r.code and r.description:
                r.display_name = f"{r.code} - {r.description}"
            else:
                r.display_name = ""
