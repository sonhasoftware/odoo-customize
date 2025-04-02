from odoo import api, fields, models


class District(models.Model):
    _name = 'district'
    _rec_name = 'district_name'

    district_code = fields.Char(string="Mã quận huyện")
    district_name = fields.Char(string="Tên quận huyện")
    province_id = fields.Many2one("province", string="Tỉnh thành")
