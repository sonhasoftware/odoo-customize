from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PurchasingGroup(models.Model):
    _name = 'purchasing.group'
    _rec_name = 'x_full_name'

    purchasing_group_code = fields.Char("Mã nhóm mua hàng")
    description = fields.Char("Mô tả")
    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('purchasing_group_code', 'description')
    def get_full_name(self):
        for r in self:
            if r.purchasing_group_code and r.description:
                r.x_full_name = f"[{r.purchasing_group_code}] {r.description}"
            else:
                r.x_full_name = ""
