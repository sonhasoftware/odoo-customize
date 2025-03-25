from odoo import api, fields, models

class PhuongXa(models.Model):
    _name = 'ward.commune'
    _rec_name = 'ward_commune_name'

    ward_commune_code = fields.Char(string="Mã phường xã")
    ward_commune_name = fields.Text(string="Tên phường xã")
    district_id = fields.Many2one("district", string="Quận/huyện")