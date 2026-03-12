from odoo import api, fields, models


class MDMHhType(models.Model):
    _name = 'mdm.hh.type'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
