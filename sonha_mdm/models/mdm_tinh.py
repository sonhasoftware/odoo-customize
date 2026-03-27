from odoo import api, fields, models


class MDMTinh(models.Model):
    _name = 'mdm.tinh'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
