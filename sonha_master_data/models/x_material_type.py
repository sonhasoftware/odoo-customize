from odoo import fields, models, api


class XMaterialType(models.Model):
    _name = 'x.material.type'
    _rec_name = 'x_full_name'

    name = fields.Char("Tên", required=True)
    x_code = fields.Char("Mã loại vật tư", required=True)
    x_qty_manage = fields.Boolean(string="Quản lý số lượng")
    x_value_manage = fields.Boolean(string="Quản lý giá trị")
    x_price_type = fields.Selection(string='Loại giá', selection=[('s', 'S'), ('v', 'V')])

    x_full_name = fields.Char("Tên đầy đủ", compute="get_full_name", store=True)

    @api.depends('name', 'x_code')
    def get_full_name(self):
        for r in self:
            if r.name and r.x_code:
                r.x_full_name = f"{r.x_code}: {r.name}"
            else:
                r.x_full_name = ""

