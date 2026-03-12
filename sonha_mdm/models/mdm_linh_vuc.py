from odoo import api, fields, models


class MDMLinhVuc(models.Model):
    _name = 'mdm.linh.vuc'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
    key_map = fields.Integer("Key domain")
