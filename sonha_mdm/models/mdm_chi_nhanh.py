from odoo import api, fields, models


class MDMChiNhanh(models.Model):
    _name = 'mdm.chi.nhanh'
    _rec_name = 'ma'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
