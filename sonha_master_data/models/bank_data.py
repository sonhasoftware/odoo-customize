from odoo import models, fields, api


class BankData(models.Model):
    _name = 'bank.data'
    _rec_name = 'display_name'

    bank_country = fields.Many2one('bank.country', string="Quốc gia")
    bank_key = fields.Char("Số ngân hàng")
    bank_name = fields.Char("Tên ngân hàng")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('bank_key', 'bank_name')
    def compute_display_name(self):
        for r in self:
            if r.bank_key and r.bank_name:
                r.display_name = f"{r.bank_key} - {r.bank_name}"
            else:
                r.display_name = False
