from odoo import api, fields, models


class MienLon(models.Model):
    _name = 'mien.lon'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
