# -*- coding: utf-8 -*-
from odoo import fields, models


class TongHopVatTu(models.Model):
    _name = 'tong.hop.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tổng hợp vật tư'
    _order = 'period_id, company_id, don_vi_kd_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', index=True,
        help='Công ty sản xuất/kho (BNH, SSP).')
    don_vi_kd_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng', index=True,
        help='Đơn vị kinh doanh (SHI, TM1…). Trống = dòng gộp all KD cho B5.')
    ma_dat_hang = fields.Char(string='Mã đặt hàng', index=True)
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')

    ton_dau = fields.Float(string='Tồn đầu', digits=(16, 3))
    don_gia_ton_kho = fields.Float(
        string='Đơn giá tồn kho',
        digits=(16, 2),
        help='Đơn giá SAP đầu tháng T-1 (tien_ton_dau/ton_dau). B5 đọc từ đây, không query lại SAP.',
    )

    # Vật tư đi đường (gộp từ import đơn vị KD): SL + ĐG + GT theo tháng
    ve_du_kien_don_vi_t0 = fields.Float(string='Hàng đi đường T0', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t1 = fields.Float(string='Hàng đi đường T1', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t2 = fields.Float(string='Hàng đi đường T2', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t3 = fields.Float(string='Hàng đi đường T3', digits=(16, 3), readonly=True)
    ve_du_kien_don_gia_t0 = fields.Float(string='Đi đường ĐG T0', digits=(16, 2), readonly=True)
    ve_du_kien_don_gia_t1 = fields.Float(string='Đi đường ĐG T1', digits=(16, 2), readonly=True)
    ve_du_kien_don_gia_t2 = fields.Float(string='Đi đường ĐG T2', digits=(16, 2), readonly=True)
    ve_du_kien_don_gia_t3 = fields.Float(string='Đi đường ĐG T3', digits=(16, 2), readonly=True)
    ve_du_kien_gia_tri_t0 = fields.Float(string='Đi đường GT T0', digits=(16, 2), readonly=True)
    ve_du_kien_gia_tri_t1 = fields.Float(string='Đi đường GT T1', digits=(16, 2), readonly=True)
    ve_du_kien_gia_tri_t2 = fields.Float(string='Đi đường GT T2', digits=(16, 2), readonly=True)
    ve_du_kien_gia_tri_t3 = fields.Float(string='Đi đường GT T3', digits=(16, 2), readonly=True)

    vt_can_dung_t0 = fields.Float(string='Cần dùng T0', digits=(16, 3))
    vt_can_dung_t1 = fields.Float(string='Cần dùng T1', digits=(16, 3))
    vt_can_dung_t2 = fields.Float(string='Cần dùng T2', digits=(16, 3))
    vt_can_dung_t3 = fields.Float(string='Cần dùng T3', digits=(16, 3))

    ton_cuoi_t0 = fields.Float(string='Tồn cuối T0', digits=(16, 3))
    ton_cuoi_t1 = fields.Float(string='Tồn cuối T1', digits=(16, 3))
    ton_cuoi_t2 = fields.Float(string='Tồn cuối T2', digits=(16, 3))
    ton_cuoi_t3 = fields.Float(string='Tồn cuối T3', digits=(16, 3))

    so_luong_du_phong = fields.Float(string='Dự phòng', digits=(16, 3))
    so_luong_thieu = fields.Float(string='Thiếu', digits=(16, 3))
    so_luong_can_mua = fields.Float(string='Cần mua', digits=(16, 3))

    ghi_chu = fields.Char(string='Ghi chú')
