from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ItemCategoryGroup(models.Model):
    _name = 'item.category.group'
    _rec_name = 'category_group_code'

    category_group_code = fields.Char("Mã nhóm loại hàng")
    description = fields.Char("Diễn giải")
    note = fields.Text("Ghi chú")