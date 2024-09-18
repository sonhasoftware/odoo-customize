from odoo import api, fields, models

class ConfigReason(models.Model):
    _name='config.reason'

    name = fields.Char(string='Tên lý do')
    type_leave = fields.Many2one('config.word.slip', string='Loại nghỉ')
    accept_require = fields.Boolean(string='Yêu cầu chốt')
    count_work = fields.Boolean(string='Tính công')
    fine = fields.Boolean(string='Phạt tiền')
    max_leave = fields.Integer(string='Số lần tối đa')
    business_fee = fields.Float(string='Phí công tác')