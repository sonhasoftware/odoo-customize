from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BPType(models.Model):
    _name = 'bp.type'
    _rec_name = 'display_name'

    type_code = fields.Char("Mã loại BP", required=True)
    type_name = fields.Char("Tên loại BP", required=True)
    display_name = fields.Char(compute="filter_display_name", store=True)

    @api.depends('type_code', 'type_name')
    def filter_display_name(self):
        for r in self:
            if r.type_code and r.type_name:
                r.display_name = f"{r.type_code} - {r.type_name}"
            else:
                r.display_name = False
