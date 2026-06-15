from odoo import api, fields, models


class ExcelHangHoaLine(models.Model):
    _name = 'excel.hang.hoa.line'

    ma = fields.Char("Mã excel", index=True, store=True)
    ten = fields.Char("Tên excel", index=True, store=True)
    ma_mdm = fields.Char("Mã mdm", index=True, store=True)
    ten_mdm = fields.Char("Tên mdm", index=True, store=True)
    percent = fields.Float("% Giống nhau", store=True)
    key = fields.Many2one('excel.hang.hoa')

