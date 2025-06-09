from odoo import fields, models, api

class XProductxHierarchy(models.Model):
    _name = 'x.product.hierarchy'
    _rec_name = 'x_full_name'

    name = fields.Char("Tên", required=True)
    code = fields.Char("Mã PRH", required=True)
    level = fields.Integer("Cấp độ")
    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'code')
    def get_full_name(self):
        for r in self:
            if r.name and r.code:
                r.x_full_name = f"[{r.code}] {r.name}"
            else:
                r.x_full_name = ""
