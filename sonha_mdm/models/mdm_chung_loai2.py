from odoo import api, fields, models


class MDMChungLoai2(models.Model):
    _name = 'mdm.chung.loai2'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key = fields.Many2one('mdm.chung.loai1', string="Key mapping")
    key_linh_vuc = fields.Integer("Key lĩnh vực")
    key_nganh_hang = fields.Integer("Key ngành hàng")
    key_nhan_hang = fields.Integer("Key nhãn hàng")
