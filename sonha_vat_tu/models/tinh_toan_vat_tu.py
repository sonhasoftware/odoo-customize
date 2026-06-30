# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TinhToanVatTu(models.Model):
    _name = 'tinh.toan.vat.tu'
    _description = 'Tính toán vật tư'
    _order = 'period_id, ma_vat_tu, don_vi_kd_id, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', index=True,
        help='Công ty sản xuất/kho (BNH, SSP) — dùng cho B4/B5.')
    don_vi_kd_id = fields.Many2one(
        'res.company', string='Đơn vị KD', index=True,
        help='Đơn vị kế hoạch kinh doanh (SHI, TM1, TM2, NAN…).')
    don_vi_kd_code = fields.Char(
        string='Mã đơn vị KD',
        compute='_compute_don_vi_kd_code',
        store=True,
        readonly=True,
    )
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

    _sql_constraints = [
        ('uniq_b3_kd_material',
         'unique(period_id, company_id, don_vi_kd_id, ma_vat_tu)',
         'Trùng dòng B3: Kỳ, Đơn vị SX, Đơn vị KD và Mã NVL phải duy nhất!'),
    ]

    @api.depends('don_vi_kd_id')
    def _compute_don_vi_kd_code(self):
        for rec in self:
            company = rec.don_vi_kd_id
            if not company:
                rec.don_vi_kd_code = False
            else:
                rec.don_vi_kd_code = company.company_code or company.name
