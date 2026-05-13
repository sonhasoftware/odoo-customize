# -*- coding: utf-8 -*-
from odoo import fields, models


class DinhMuc(models.Model):
    _name = 'dinh.muc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Định mức tháng'
    _order = 'period_id, company_id, month_key, ma_tp, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', index=True,
        default=lambda self: self.env.company)

    ma_sap = fields.Char(string='Mã SAP')
    ten_sap = fields.Char(string='Tên SAP')
    ma_tp = fields.Char(string='Mã thành phẩm', index=True)
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    month_key = fields.Char(string='Tháng')
    qty = fields.Float(string='Số lượng', digits=(16, 2))
