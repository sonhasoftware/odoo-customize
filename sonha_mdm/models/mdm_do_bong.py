from odoo import api, fields, models


class MDMDoBong(models.Model):
    _name = 'mdm.do.bong'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True)
    ten = fields.Text("Tên", store=True)
