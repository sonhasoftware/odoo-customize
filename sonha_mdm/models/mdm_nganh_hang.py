from odoo import api, fields, models


class MDMNganhHang(models.Model):
    _name = 'mdm.nganh.hang'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
