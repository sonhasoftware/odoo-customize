from odoo import api, fields, models


class MDMDungTich(models.Model):
    _name = 'mdm.dung.tich'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
