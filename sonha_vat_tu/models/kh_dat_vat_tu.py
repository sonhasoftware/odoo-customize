# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KhDatVatTu(models.Model):
    _name = 'kh.dat.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Kế hoạch đặt vật tư'
    _order = 'period_id, company_id, ma_sap, month_date, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')

    tong_ton_nvl_sl = fields.Float(string='Tồn NVL', digits=(16, 3))
    tong_hang_di_duong_sl = fields.Float(string='Hàng đi đường', digits=(16, 3))
    tong_sl_vt_can_dung = fields.Float(string='VT cần dùng', digits=(16, 3))
    sl_du_tru_toi_thieu = fields.Float(string='Dự trữ tối thiểu', digits=(16, 3))
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua theo MOQ', digits=(16, 3))

    sl_dat_mua_de_xuat = fields.Float(
        string='SL đặt mua đề xuất', compute='_compute_core_values', store=True, digits=(16, 3))
    sl_dat_mua_chot = fields.Float(
        string='SL đặt mua chốt', compute='_compute_core_values', store=True, digits=(16, 3))
    sl_ton_kho = fields.Float(
        string='SL tồn sau mua', compute='_compute_core_values', store=True, digits=(16, 3))
    so_ngay_vong_quay_ton = fields.Float(
        string='Ngày vòng quay tồn', compute='_compute_core_values', store=True, digits=(16, 2))
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
