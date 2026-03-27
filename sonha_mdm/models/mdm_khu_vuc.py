from odoo import api, fields, models


class MDMKhuVuc(models.Model):
    _name = 'mdm.khu.vuc'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
