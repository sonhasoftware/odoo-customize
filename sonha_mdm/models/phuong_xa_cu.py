from odoo import api, fields, models


class PhuongXaCu(models.Model):
    _name = 'phuong.xa.cu'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
