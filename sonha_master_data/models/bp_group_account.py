from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BPGroupAccount(models.Model):
    _name = 'bp.group.account'
    _rec_name = 'display_name'

    group_code = fields.Char("Mã nhóm BP", required=True)
    group_name = fields.Char("Tên nhóm BP", required=True)
    display_name = fields.Char(compute="filter_display_name", store=True)

    @api.depends('group_code', 'group_name')
    def filter_display_name(self):
        for r in self:
            if r.group_code and r.group_name:
                r.display_name = f"{r.group_code} - {r.group_name}"
            else:
                r.display_name = False
