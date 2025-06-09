from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ItemCategoryGroup(models.Model):
    _name = 'item.category.group'
    _rec_name = 'x_full_name'

    category_group_code = fields.Char("Mã nhóm loại hàng", required=True)
    description = fields.Char("Diễn giải", required=True)
    note = fields.Text("Ghi chú")
    sale_org = fields.Many2many('sale.organization', string="Tổ chức kinh doanh")
    distb_channel = fields.Many2many('distribution.channel', string="Kênh")
    mat_type = fields.Many2many('x.material.type', string="Loại vật tư")

    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('category_group_code', 'description')
    def get_full_name(self):
        for r in self:
            if r.category_group_code and r.description:
                r.x_full_name = f"{r.category_group_code} - {r.description}"
            else:
                r.x_full_name = ""

