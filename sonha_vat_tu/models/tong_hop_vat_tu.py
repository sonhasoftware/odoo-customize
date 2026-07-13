# -*- coding: utf-8 -*-
from odoo import api, fields, models

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
        help='Đơn vị kinh doanh (SHI, TM1…). Trống = dòng gộp all KD cho BCU/B5.')
    ma_dat_hang = fields.Char(string='Mã đặt hàng', index=True)
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')

    # Tồn đầu: chỉ có 1 giá trị duy nhất (đầu kỳ)
    ton_dau = fields.Float(string='Tồn đầu', digits=(16, 3))

    # Hàng đi đường: từ import vật tư đi đường (menu chính)
    ve_du_kien_don_vi_t0 = fields.Float(string='Hàng đi đường ĐV T0', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t1 = fields.Float(string='Hàng đi đường ĐV T1', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t2 = fields.Float(string='Hàng đi đường ĐV T2', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi_t3 = fields.Float(string='Hàng đi đường ĐV T3', digits=(16, 3), readonly=True)

    # Hàng đi đường BCU: import Excel trên B4, chỉ để đối chiếu (không ảnh hưởng tồn cuối/thiếu)
    ve_du_kien_t0 = fields.Float(
        string='Hàng đi đường BCU T0', digits=(16, 3), readonly=True,
        help='Số liệu BCU import để so sánh. Không dùng trong công thức tồn cuối/thiếu.')
    ve_du_kien_t1 = fields.Float(
        string='Hàng đi đường BCU T1', digits=(16, 3), readonly=True,
        help='Số liệu BCU import để so sánh. Không dùng trong công thức tồn cuối/thiếu.')
    ve_du_kien_t2 = fields.Float(
        string='Hàng đi đường BCU T2', digits=(16, 3), readonly=True,
        help='Số liệu BCU import để so sánh. Không dùng trong công thức tồn cuối/thiếu.')
    ve_du_kien_t3 = fields.Float(
        string='Hàng đi đường BCU T3', digits=(16, 3), readonly=True,
        help='Số liệu BCU import để so sánh. Không dùng trong công thức tồn cuối/thiếu.')

    # Cần dùng: chia theo 4 tháng
    vt_can_dung_t0 = fields.Float(string='Cần dùng T0', digits=(16, 3))
    vt_can_dung_t1 = fields.Float(string='Cần dùng T1', digits=(16, 3))
    vt_can_dung_t2 = fields.Float(string='Cần dùng T2', digits=(16, 3))
    vt_can_dung_t3 = fields.Float(string='Cần dùng T3', digits=(16, 3))

    # Tồn cuối: chia theo 4 tháng (dồn lũy kế)
    ton_cuoi_t0 = fields.Float(string='Tồn cuối T0', digits=(16, 3))
    ton_cuoi_t1 = fields.Float(string='Tồn cuối T1', digits=(16, 3))
    ton_cuoi_t2 = fields.Float(string='Tồn cuối T2', digits=(16, 3))
    ton_cuoi_t3 = fields.Float(string='Tồn cuối T3', digits=(16, 3))

    # Dự phòng, Thiếu, Cần mua: chỉ 1 giá trị cuối kỳ
    so_luong_du_phong = fields.Float(string='Dự phòng', digits=(16, 3))
    so_luong_thieu = fields.Float(string='Thiếu', digits=(16, 3))
    so_luong_can_mua = fields.Float(string='Cần mua', digits=(16, 3))

    ghi_chu = fields.Char(string='Ghi chú')
