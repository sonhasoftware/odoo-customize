from odoo import models, fields, api


class CusGroup(models.Model):
    _name = 'cus.group'
    _rec_name = 'display_name'

    sap_code = fields.Char("Mã SAP")
    symbol = fields.Char("Ký hiệu")
    description = fields.Char("Diễn giải")
    note = fields.Text("Ghi chú")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('symbol', 'description')
    def compute_display_name(self):
        for r in self:
            if r.symbol and r.description:
                r.display_name = f"{r.symbol} - {r.description}"
            else:
                r.display_name = ""
