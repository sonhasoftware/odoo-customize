from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class CustomerGroup(models.Model):
    _name = 'customer.group'
    _rec_name = 'display_name'

    customer_group_code = fields.Char("Mã nhóm khách hàng", required=True)
    customer_group_name = fields.Char("Tên nhóm khách hàng", required=True)
    display_name = fields.Char(compute="filter_display_name", store=True)

    @api.depends('customer_group_code', 'customer_group_name')
    def filter_display_name(self):
        for r in self:
            if r.customer_group_code and r.customer_group_name:
                r.display_name = f"{r.customer_group_code} - {r.customer_group_name}"
            else:
                r.display_name = False
