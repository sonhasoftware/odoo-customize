# -*- coding: utf-8 -*-
from odoo import api, fields, models


class KhDatVatTu(models.Model):
    _name = 'kh.dat.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Kế hoạch đặt vật tư'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        related='company_id.currency_id',
        readonly=True,
    )
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    chung_loai = fields.Char(string='Chủng loại')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')

    tong_ton_nvl_sl = fields.Float(string='Tồn NVL đầu kỳ', digits=(16, 3))
    don_gia_ton_kho = fields.Monetary(
        string='Đơn giá tồn kho', currency_field='currency_id')
    gia_tri_ton_nvl_dau_ky = fields.Monetary(
        string='Giá trị tồn NVL',
        compute='_compute_gia_tri_ton_nvl_dau_ky',
        currency_field='currency_id',
    )

    @api.depends('tong_ton_nvl_sl', 'don_gia_ton_kho')
    def _compute_gia_tri_ton_nvl_dau_ky(self):
        for rec in self:
            rec.gia_tri_ton_nvl_dau_ky = (
                (rec.tong_ton_nvl_sl or 0.0) * (rec.don_gia_ton_kho or 0.0)
            )

    tong_sl_vt_can_dung_t0 = fields.Float(string='Cần dùng T0', digits=(16, 3))
    tong_sl_vt_can_dung_t1 = fields.Float(string='Cần dùng T1', digits=(16, 3))
    tong_sl_vt_can_dung_t2 = fields.Float(string='Cần dùng T2', digits=(16, 3))
    tong_sl_vt_can_dung_t3 = fields.Float(string='Cần dùng T3', digits=(16, 3))
    tong_vt_can_dung = fields.Float(string='Tổng cần dùng', digits=(16, 3))

    tong_hang_di_duong_sl_t0 = fields.Float(string='Đi đường T0', digits=(16, 3))
    tong_hang_di_duong_sl_t1 = fields.Float(string='Đi đường T1', digits=(16, 3))
    tong_hang_di_duong_sl_t2 = fields.Float(string='Đi đường T2', digits=(16, 3))
    tong_hang_di_duong_sl_t3 = fields.Float(string='Đi đường T3', digits=(16, 3))
    tong_hang_di_duong = fields.Float(string='Tổng đi đường', digits=(16, 3))

    sl_du_tru_toi_thieu = fields.Float(string='Dự trữ tối thiểu', digits=(16, 3))
    sl_dat_mua_de_xuat = fields.Float(string='SL đặt mua đề xuất', digits=(16, 3))
    sl_dat_mua_chot = fields.Float(string='SL đặt mua chốt', digits=(16, 3))
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua theo MOQ', digits=(16, 3))
    don_gia_mua = fields.Monetary(
        string='Đơn giá mua', currency_field='currency_id')
    gia_tri_mua_hang = fields.Monetary(
        string='Giá trị mua hàng',
        compute='_compute_b5_derived',
        store=True,
        currency_field='currency_id',
    )
    sl_ton_kho_cuoi_ky = fields.Float(
        string='Tồn kho cuối kỳ',
        compute='_compute_b5_derived',
        store=True,
        digits=(16, 3),
    )
    vt_loi_ton_lau = fields.Float(string='VT lỗi, tồn lâu ngày', digits=(16, 3))
    so_ngay_vong_quay_ton = fields.Float(
        string='Ngày vòng quay tồn kho',
        compute='_compute_b5_derived',
        store=True,
        digits=(16, 2),
    )
    don_gia_ton_kho_cuoi_ky = fields.Monetary(
        string='Đơn giá tồn cuối kỳ',
        compute='_compute_b5_derived',
        store=True,
        currency_field='currency_id',
    )
    gia_tri_ton_kho_cuoi_ky = fields.Monetary(
        string='Giá trị tồn kho cuối kỳ',
        compute='_compute_b5_derived',
        store=True,
        currency_field='currency_id',
    )

    ghi_chu = fields.Char(string='Ghi chú')

    @staticmethod
    def _count_months_with_can_dung(t0, t1, t2, t3):
        return sum(1 for qty in (t0, t1, t2, t3) if (qty or 0.0) > 0)

    def _b5_derived_values(self):
        """Cong thuc Excel: ton cuoi, vong quay, don gia/gia tri ton cuoi."""
        self.ensure_one()
        ton_dau = self.tong_ton_nvl_sl or 0.0
        tdd = self.tong_hang_di_duong or 0.0
        moq = self.sl_can_mua_theo_moq or 0.0
        tcd = self.tong_vt_can_dung or 0.0
        gia_tri_ton_dau = ton_dau * (self.don_gia_ton_kho or 0.0)
        gia_tri_mua = moq * (self.don_gia_mua or 0.0)

        ton_cuoi = ton_dau - tcd + tdd + moq
        n_months = self._count_months_with_can_dung(
            self.tong_sl_vt_can_dung_t0,
            self.tong_sl_vt_can_dung_t1,
            self.tong_sl_vt_can_dung_t2,
            self.tong_sl_vt_can_dung_t3,
        )
        if tcd > 0 and n_months > 0:
            vong_quay = ton_cuoi * 30.0 / (tcd / n_months)
        else:
            vong_quay = 0.0

        mau_so_gia = ton_dau + tdd + moq
        if mau_so_gia > 0:
            don_gia_cuoi = (gia_tri_ton_dau + gia_tri_mua) / mau_so_gia
        else:
            don_gia_cuoi = 0.0

        return {
            'sl_ton_kho_cuoi_ky': ton_cuoi,
            'so_ngay_vong_quay_ton': vong_quay,
            'don_gia_ton_kho_cuoi_ky': don_gia_cuoi,
            'gia_tri_ton_kho_cuoi_ky': don_gia_cuoi * ton_cuoi,
            'gia_tri_mua_hang': gia_tri_mua,
        }

    @api.depends(
        'tong_ton_nvl_sl',
        'tong_vt_can_dung',
        'tong_hang_di_duong',
        'sl_can_mua_theo_moq',
        'don_gia_mua',
        'don_gia_ton_kho',
        'tong_sl_vt_can_dung_t0',
        'tong_sl_vt_can_dung_t1',
        'tong_sl_vt_can_dung_t2',
        'tong_sl_vt_can_dung_t3',
    )
    def _compute_b5_derived(self):
        for rec in self:
            derived = rec._b5_derived_values()
            rec.sl_ton_kho_cuoi_ky = derived['sl_ton_kho_cuoi_ky']
            rec.so_ngay_vong_quay_ton = derived['so_ngay_vong_quay_ton']
            rec.don_gia_ton_kho_cuoi_ky = derived['don_gia_ton_kho_cuoi_ky']
            rec.gia_tri_ton_kho_cuoi_ky = derived['gia_tri_ton_kho_cuoi_ky']
            rec.gia_tri_mua_hang = derived['gia_tri_mua_hang']
