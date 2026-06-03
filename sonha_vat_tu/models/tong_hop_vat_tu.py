# -*- coding: utf-8 -*-
from odoo import fields, models


class TongHopVatTu(models.Model):
    _name = 'tong.hop.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tổng hợp vật tư cần sản xuất'
    _order = 'period_id, company_id, ma_sap, month_date, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_dat_hang = fields.Char(string='Mã đặt hàng', index=True)
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)

    ton_dau = fields.Float(string='Tồn đầu', digits=(16, 3))
    ve_du_kien = fields.Float(string='Vật tư đi đường', digits=(16, 3))
    vt_can_dung = fields.Float(string='VT cần dùng', digits=(16, 3))
    ton_cuoi = fields.Float(string='Tồn cuối', digits=(16, 3))

    so_luong_du_phong = fields.Float(string='SL dự phòng', digits=(16, 3))
    so_luong_thieu = fields.Float(string='SL thiếu', digits=(16, 3))
    so_luong_can_mua = fields.Float(string='SL cần mua', digits=(16, 3))
    ghi_chu = fields.Char(string='Ghi chú')
