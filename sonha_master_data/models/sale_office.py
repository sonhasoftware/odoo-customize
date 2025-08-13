from odoo import models, fields, api


class SaleOffice(models.Model):
    _name = 'sale.office'
    _rec_name = 'display_name'

    branch_code = fields.Char("Mã chi nhánh")
    current_branch_code = fields.Char("Mã chi nhánh hiện tại")
    name = fields.Char("Tên chi nhánh")

    display_name = fields.Char(compute="compute_display_name", store=True)

    @api.depends('branch_code', 'name')
    def compute_display_name(self):
        for r in self:
            if r.branch_code and r.name:
                r.display_name = f"{r.branch_code} - {r.name}"
            else:
                r.display_name = ""

