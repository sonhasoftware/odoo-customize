from odoo import api, fields, models


class SonhaMD(models.Model):
    _name = 'sonha.md'

    code = fields.Char("Mã")
    name = fields.Text("Tên")
    vector = fields.Char("Véc tơ")
