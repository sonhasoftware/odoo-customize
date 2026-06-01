# -*- coding: utf-8 -*-
from odoo import fields, models


class DinhMuc(models.Model):
    _name = 'dinh.muc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Định mức tháng'
    _order = 'period_id, company_id, month_date, ma_tp, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True,
        default=lambda self: self.env.company)

    ma_sap = fields.Char(string='Mã SAP')
    ten_sap = fields.Char(string='Tên SAP')
    ma_tp = fields.Char(string='Mã TP', index=True)
    ten_tp = fields.Char(string='Tên TP')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    month_key = fields.Char(string='Tháng')
    month_date = fields.Date(string='Tháng tính toán', index=True)
    qty_kinh_doanh = fields.Float(string='Kinh doanh', digits=(16, 2))
    qty_san_xuat = fields.Float(string='Sản xuất', digits=(16, 2))
    qty_chenh_lech = fields.Float(string='Chênh lệch', digits=(16, 2))
    qty = fields.Float(string='Số lượng', digits=(16, 2))
