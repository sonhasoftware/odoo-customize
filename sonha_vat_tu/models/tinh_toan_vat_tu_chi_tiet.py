# -*- coding: utf-8 -*-
from odoo import fields, models


class TinhToanVatTuChiTiet(models.Model):
    """Bảng chi tiết explode KHKD × BOM NVL — phục vụ soi vs Excel khi lệch B3."""

    _name = 'tinh.toan.vat.tu.chi.tiet'
    _description = 'Chi tiết tính toán vật tư (audit B3)'
    _order = 'period_id, don_vi_kd_code, ma_nvl, qty_nvl_t0 desc, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True, required=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', index=True)
    don_vi_kd_id = fields.Many2one(
        'res.company', string='Đơn vị KD', index=True)
    don_vi_kd_code = fields.Char(string='Mã đơn vị KD', index=True)

    ma = fields.Char(
        string='Mã', index=True,
        help='Mã trên kế hoạch kinh doanh (TP 10000… hoặc BTP 11000…).')
    ma_hang = fields.Char(string='Mã hàng / EFFECT', index=True)
    ten_kh = fields.Char(string='Tên')

    ma_tp_cha = fields.Char(
        string='Mã cha BOM', index=True,
        help='Tấm / xẻ trung gian trên bom_tinh_toan.')
    ten_tp_cha = fields.Char(string='Tên cha BOM')

    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')

    sl_thuc_te = fields.Float(
        string='Định mức (sl_thuc_te)', digits=(16, 6),
        help='Hệ số BOM NVL / 1 đơn vị mã KH — đối chiếu kg/tấm Excel.')
    cap_bom = fields.Integer(string='Cấp BOM')

    qty_kh_t0 = fields.Float(string='SL KH T0', digits=(16, 2))
    qty_kh_t1 = fields.Float(string='SL KH T1', digits=(16, 2))
    qty_kh_t2 = fields.Float(string='SL KH T2', digits=(16, 2))
    qty_kh_t3 = fields.Float(string='SL KH T3', digits=(16, 2))

    qty_nvl_t0 = fields.Float(
        string='SL NVL T0', digits=(16, 3),
        help='= SL KH T0 × định mức — cộng theo mã NVL + đơn vị KD = B3.')
    qty_nvl_t1 = fields.Float(string='SL NVL T1', digits=(16, 3))
    qty_nvl_t2 = fields.Float(string='SL NVL T2', digits=(16, 3))
    qty_nvl_t3 = fields.Float(string='SL NVL T3', digits=(16, 3))
