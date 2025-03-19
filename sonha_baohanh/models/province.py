from odoo import api, fields, models


class Province(models.Model):
    _name = 'province'
    _rec_name='province_name'
    province_code = fields.Char(string="Mã tỉnh thành")
    province_name = fields.Text(string="Tên tỉnh thành")
    # quan_huyen_ids = fields.One2many('quan.huyen', 'tinh_thanh_id', string='Quận/huyện')