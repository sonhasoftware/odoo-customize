# -*- coding: utf-8 -*-
from odoo import api, fields, models

class DinhMuc(models.Model):
    _name = 'dinh.muc'
    _description = 'Định mức kỳ'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    ten_sap = fields.Char(string='Tên SAP')
    ma_tp = fields.Char(string='Mã TP', index=True)
    ten_tp = fields.Char(string='Tên TP')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')

    qty_kinh_doanh_t0 = fields.Float(string='KD T0', digits=(16, 2))
    qty_kinh_doanh_t1 = fields.Float(string='KD T1', digits=(16, 2))
    qty_kinh_doanh_t2 = fields.Float(string='KD T2', digits=(16, 2))
    qty_kinh_doanh_t3 = fields.Float(string='KD T3', digits=(16, 2))

    qty_san_xuat_t0 = fields.Float(string='SX T0', digits=(16, 2))
    qty_san_xuat_t1 = fields.Float(string='SX T1', digits=(16, 2))
    qty_san_xuat_t2 = fields.Float(string='SX T2', digits=(16, 2))
    qty_san_xuat_t3 = fields.Float(string='SX T3', digits=(16, 2))

    qty_chenh_lech_t0 = fields.Float(string='CL T0', digits=(16, 2))
    qty_chenh_lech_t1 = fields.Float(string='CL T1', digits=(16, 2))
    qty_chenh_lech_t2 = fields.Float(string='CL T2', digits=(16, 2))
    qty_chenh_lech_t3 = fields.Float(string='CL T3', digits=(16, 2))

    qty_t0 = fields.Float(string='Số lượng T0', digits=(16, 3))
    qty_t1 = fields.Float(string='Số lượng T1', digits=(16, 3))
    qty_t2 = fields.Float(string='Số lượng T2', digits=(16, 3))
    qty_t3 = fields.Float(string='Số lượng T3', digits=(16, 3))
