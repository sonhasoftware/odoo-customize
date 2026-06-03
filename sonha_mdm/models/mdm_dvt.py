from odoo import fields, models


class MDMDVT(models.Model):
    _name = 'mdm.dvt'
    _rec_name = 'ten'

    ma = fields.Char("Mã", store=True, index=True)
    ten = fields.Text("Tên", store=True)
