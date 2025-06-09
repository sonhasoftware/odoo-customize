from odoo import fields, models, api

class SaleOrganization(models.Model):
    _name = 'sale.organization'
    _rec_name = 'x_full_name'

    name = fields.Char("Tên", required=True)
    company_id = fields.Many2one('res.company', string="Công ty")
    x_note = fields.Char("Ghi chú")
    code = fields.Char("Mã", required=True)

    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'code')
    def get_full_name(self):
        for r in self:
            if r.code and r.name:
                r.x_full_name = f"[{r.code}] {r.name}"
            else:
                r.x_full_name = ""

