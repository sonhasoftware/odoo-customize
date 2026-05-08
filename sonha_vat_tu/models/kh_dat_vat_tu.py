# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KhDatVatTu(models.Model):
    _name = 'kh.dat.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'B5 - Kế hoạch đặt vật tư'
    _order = 'period_id, company_id, ma_sap, month_key, id'
    _DON_VI_TINH = [
        ('kg', 'Kg'),
        ('cai', 'Cái'),
    ]

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    ma_effect = fields.Char(string='Mã effect', index=True)
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Selection(_DON_VI_TINH, string='Đơn vị tính')

    tong_ton_nvl_sl = fields.Float(string='Tổng tồn nguyên vật liệu (Số lượng)', digits=(16, 3))
    tong_hang_di_duong_sl = fields.Float(string='Tổng hàng đi đường (Số lượng)', digits=(16, 3))
    tong_sl_vt_can_dung = fields.Float(string='Tổng số lượng vật tư cần dùng', digits=(16, 3))
    sl_du_tru_toi_thieu = fields.Float(string='Số lượng dự trữ tối thiểu', digits=(16, 3))
    sl_can_mua_theo_moq = fields.Float(string='Số lượng cần mua theo MOQ', digits=(16, 3))

    sl_dat_mua_de_xuat = fields.Float(
        string='Số lượng đặt mua đề xuất', compute='_compute_core_values', store=True, digits=(16, 3))
    sl_dat_mua_chot = fields.Float(
        string='Số lượng đặt mua chốt', compute='_compute_core_values', store=True, digits=(16, 3))
    sl_ton_kho = fields.Float(
        string='Số lượng tồn kho', compute='_compute_core_values', store=True, digits=(16, 3))
    so_ngay_vong_quay_ton = fields.Float(
        string='Số ngày vòng quay tồn kho', compute='_compute_core_values', store=True, digits=(16, 2))
    don_gia_ton_kho = fields.Float(string='Đơn giá tồn kho', digits=(16, 3))
    gia_tri_ton_kho = fields.Float(
        string='Giá trị tồn kho', compute='_compute_core_values', store=True, digits=(16, 3))
    ghi_chu = fields.Char(string='Ghi chú')

    @api.depends(
        'tong_ton_nvl_sl',
        'tong_hang_di_duong_sl',
        'tong_sl_vt_can_dung',
        'sl_du_tru_toi_thieu',
        'sl_can_mua_theo_moq',
        'don_gia_ton_kho')
    def _compute_core_values(self):
        for rec in self:
            rec.sl_dat_mua_de_xuat = (
                (rec.tong_ton_nvl_sl or 0.0)
                - (rec.tong_sl_vt_can_dung or 0.0)
                + (rec.tong_hang_di_duong_sl or 0.0)
                - (rec.sl_du_tru_toi_thieu or 0.0)
            )
            rec.sl_dat_mua_chot = 0.0 if rec.sl_dat_mua_de_xuat > 0 else -rec.sl_dat_mua_de_xuat
            rec.sl_ton_kho = (
                (rec.tong_ton_nvl_sl or 0.0)
                - (rec.tong_sl_vt_can_dung or 0.0)
                + (rec.tong_hang_di_duong_sl or 0.0)
                + (rec.sl_can_mua_theo_moq or 0.0)
            )
            demand_month = rec.tong_sl_vt_can_dung or 0.0
            rec.so_ngay_vong_quay_ton = (rec.sl_ton_kho * 30.0 / demand_month) if demand_month else 0.0
            rec.gia_tri_ton_kho = (rec.sl_ton_kho or 0.0) * (rec.don_gia_ton_kho or 0.0)
