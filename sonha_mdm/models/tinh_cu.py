from odoo import api, fields, models


class TinhCu(models.Model):
    _name = 'tinh.cu'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
