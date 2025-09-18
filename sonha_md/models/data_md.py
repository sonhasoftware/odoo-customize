from odoo import api, fields, models


class DataMD(models.Model):
    _name = 'data.md'

    code = fields.Char("Mã")
    name = fields.Text("Tên")
    ti_le = fields.Float("% giống nhau")
    vat_tu = fields.Many2one('hang.hoa.vat.tu')
