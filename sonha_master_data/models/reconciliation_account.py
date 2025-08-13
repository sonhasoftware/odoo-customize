from odoo import models, fields, api


class ReconciliationAccount(models.Model):
    _name = 'reconciliation.account'
    _rec_name = 'display_name'

    name = fields.Char("Tài khoản")
    description = fields.Char("Mô tả")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('name', 'description')
    def compute_display_name(self):
        for r in self:
            if r.name and r.description:
                r.display_name = f"{r.name} - {r.description}"
            else:
                r.display_name = ""
