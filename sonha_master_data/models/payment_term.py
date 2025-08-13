from odoo import models, fields, api


class PaymentTerm(models.Model):
    _name = 'payment.term'
    _rec_name = 'display_name'

    name = fields.Char("Điều khoản thanh toán")
    description = fields.Char("Diễn giải")
    recipe = fields.Char("Công thức")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('name', 'description')
    def compute_display_name(self):
        for r in self:
            if r.name and r.description:
                r.display_name = f"{r.name} - {r.description}"
            else:
                r.display_name = ""
