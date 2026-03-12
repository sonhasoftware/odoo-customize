from odoo import api, fields, models


class MDMDoDay(models.Model):
    _name = 'mdm.do.day'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
