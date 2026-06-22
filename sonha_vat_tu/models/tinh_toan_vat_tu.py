# -*- coding: utf-8 -*-
from odoo import api, fields, models

class TinhToanVatTu(models.Model):
    _name = 'tinh.toan.vat.tu'
    _description = 'Tính toán vật tư'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    ma_vat_tu = fields.Char(string='Mã NVL', index=True)
    ten_vat_tu = fields.Char(string='Tên NVL')
    ma_effect = fields.Char(string='Mã effect')
    ten_sap = fields.Char(string='Tên SAP')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')
    do_day = fields.Float(string='Độ dày', digits=(16, 2))
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0))
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0))
    trong_luong_kg_tam = fields.Float(
        string='Trọng lượng kg/1 tấm', digits=(16, 8))
    sl_dinh_muc = fields.Float(
        string='SL định mức / 1 SP', digits=(16, 3))

    qty_t0 = fields.Float(string='Số lượng T0', digits=(16, 3))
    qty_t1 = fields.Float(string='Số lượng T1', digits=(16, 3))
    qty_t2 = fields.Float(string='Số lượng T2', digits=(16, 3))
    qty_t3 = fields.Float(string='Số lượng T3', digits=(16, 3))
