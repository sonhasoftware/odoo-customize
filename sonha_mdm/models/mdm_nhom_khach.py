from odoo import api, fields, models


class MDMNhomKhach(models.Model):
    _name = 'mdm.nhom.khach'
    _rec_name = 'ma'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
