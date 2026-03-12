from odoo import api, fields, models


class MDMChungLoai1(models.Model):
    _name = 'mdm.chung.loai1'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
