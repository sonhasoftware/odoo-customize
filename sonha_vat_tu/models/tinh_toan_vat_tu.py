# -*- coding: utf-8 -*-
from odoo import fields, models


class TinhToanVatTu(models.Model):
    _name = 'tinh.toan.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tính toán vật tư'
    _order = 'period_id, ma_sap, month_date, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    ma_vat_tu = fields.Char(string='Mã nguyên vật liệu', index=True)
    ten_vat_tu = fields.Char(string='Tên nguyên vật liệu')
    ma_effect = fields.Char(string='Mã effect', index=True)
    ten_sap = fields.Char(string='Tên SAP')
    don_vi_tinh = fields.Many2one('uom.uom', string='Đơn vị tính')
    do_day = fields.Float(string='Độ dày', digits=(16, 4))
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 3))
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 3))
    trong_luong_kg_tam = fields.Float(string='Trọng lượng kg/1 tấm', digits=(16, 8))
    sl_dinh_muc = fields.Float(
        string='Số lượng định mức / 1 sản phẩm', digits=(16, 3))
    month_key = fields.Char(string='Tháng')
    month_date = fields.Date(string='Tháng tính toán', index=True)
    qty = fields.Float(string='Số lượng', digits=(16, 2))
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
