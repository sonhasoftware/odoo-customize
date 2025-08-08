from odoo import models, fields, api


class CusIncoterm(models.Model):
    _name = 'cus.incoterm'
    _rec_name = 'display_name'

    code = fields.Char("Mã Incoterm")
    description = fields.Char("Diễn giải")
    note = fields.Text("Ghi chú")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('code', 'description')
    def compute_display_name(self):
        for r in self:
            if r.code and r.description:
                r.display_name = f"{r.code} - {r.description}"
            else:
                r.display_name = ""
