from odoo import api, fields, models


class ConfigWordSlip(models.Model):
    _name = 'config.word.slip'

    name = fields.Char("Tên đơn từ")
    paid = fields.Boolean("Tính tiền", default=False)
    max_time = fields.Float("Giờ tối đa không tính phép")
    description = fields.Text("Lý do")
    company_id = fields.Many2one('res.company', string="Công ty")

    date_and_time = fields.Selection([
        ('time', 'Chọn giờ'),
        ('date', 'Chọn ngày'),
    ], string='Dữ liệu cho kiểu nghỉ')
