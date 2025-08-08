from odoo import models, fields, api


class CusPaymentMethod(models.Model):
    _name = 'cus.payment.method'

    code = fields.Char("Mã phương thức")
    name = fields.Char("Tên phương thức")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('code', 'name')
    def compute_display_name(self):
        for r in self:
            if r.code and r.name:
                r.display_name = f"{r.code} - {r.name}"
            else:
                r.display_name = ""
