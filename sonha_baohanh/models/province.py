from odoo import api, fields, models


class Province(models.Model):
    _name = 'province'
    _rec_name='province_name'

    province_code = fields.Char(string="Mã tỉnh thành")
    province_name = fields.Char(string="Tên tỉnh thành")