# -*- coding: utf-8 -*-
from markupsafe import Markup, escape

from odoo import api, fields, models

_B6_TRACKED_FIELDS = {
    'sl_dat_mua_chot': 'Đặt mua chốt BCU',
    'sl_can_mua_theo_moq': 'SL cần mua dựa theo MOQ NCC',
}


class KhDatVatTuBcu(models.Model):
    _name = 'kh.dat.vat.tu.bcu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Tổng hợp kế hoạch vật tư BCU'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', index=True)
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

    # Hàng đi đường đơn vị (copy từ B5)
    tong_hang_di_duong_sl_t0 = fields.Float(string='ĐV đi đường SL T0', digits=(16, 3))
    tong_hang_di_duong_sl_t1 = fields.Float(string='ĐV đi đường SL T1', digits=(16, 3))
    tong_hang_di_duong_sl_t2 = fields.Float(string='ĐV đi đường SL T2', digits=(16, 3))
    tong_hang_di_duong_sl_t3 = fields.Float(string='ĐV đi đường SL T3', digits=(16, 3))
    tong_hang_di_duong_dg_t0 = fields.Monetary(
        string='ĐV đi đường ĐG T0', currency_field='currency_id')
    tong_hang_di_duong_dg_t1 = fields.Monetary(
        string='ĐV đi đường ĐG T1', currency_field='currency_id')
    tong_hang_di_duong_dg_t2 = fields.Monetary(
        string='ĐV đi đường ĐG T2', currency_field='currency_id')
    tong_hang_di_duong_dg_t3 = fields.Monetary(
        string='ĐV đi đường ĐG T3', currency_field='currency_id')
    tong_hang_di_duong_gt_t0 = fields.Monetary(
        string='ĐV đi đường GT T0', currency_field='currency_id')
    tong_hang_di_duong_gt_t1 = fields.Monetary(
        string='ĐV đi đường GT T1', currency_field='currency_id')
    tong_hang_di_duong_gt_t2 = fields.Monetary(
        string='ĐV đi đường GT T2', currency_field='currency_id')
    tong_hang_di_duong_gt_t3 = fields.Monetary(
        string='ĐV đi đường GT T3', currency_field='currency_id')
    tong_hang_di_duong = fields.Float(string='Tổng SL đi đường ĐV', digits=(16, 3))
    tong_gia_tri_di_duong = fields.Monetary(
        string='Tổng GT đi đường ĐV', currency_field='currency_id')

    # Hàng đi đường BCU (import tại B6)
    ve_du_kien_bcu_t0 = fields.Float(string='BCU đi đường SL T0', digits=(16, 3))
    ve_du_kien_bcu_t1 = fields.Float(string='BCU đi đường SL T1', digits=(16, 3))
    ve_du_kien_bcu_t2 = fields.Float(string='BCU đi đường SL T2', digits=(16, 3))
    ve_du_kien_bcu_t3 = fields.Float(string='BCU đi đường SL T3', digits=(16, 3))
    ve_du_kien_bcu_dg_t0 = fields.Monetary(
        string='BCU đi đường ĐG T0', currency_field='currency_id')
    ve_du_kien_bcu_dg_t1 = fields.Monetary(
        string='BCU đi đường ĐG T1', currency_field='currency_id')
    ve_du_kien_bcu_dg_t2 = fields.Monetary(
        string='BCU đi đường ĐG T2', currency_field='currency_id')
    ve_du_kien_bcu_dg_t3 = fields.Monetary(
        string='BCU đi đường ĐG T3', currency_field='currency_id')
    ve_du_kien_bcu_gt_t0 = fields.Monetary(
        string='BCU đi đường GT T0', currency_field='currency_id')
    ve_du_kien_bcu_gt_t1 = fields.Monetary(
        string='BCU đi đường GT T1', currency_field='currency_id')
    ve_du_kien_bcu_gt_t2 = fields.Monetary(
        string='BCU đi đường GT T2', currency_field='currency_id')
    ve_du_kien_bcu_gt_t3 = fields.Monetary(
        string='BCU đi đường GT T3', currency_field='currency_id')
    tong_ve_du_kien_bcu = fields.Float(string='Tổng SL đi đường BCU', digits=(16, 3))
    tong_gia_tri_bcu = fields.Monetary(
        string='Tổng GT đi đường BCU', currency_field='currency_id')

    sl_du_tru_toi_thieu = fields.Float(string='Dự trữ tối thiểu', digits=(16, 3))
    sl_dat_mua_de_xuat = fields.Float(
        string='SL đặt mua đề xuất',
        compute='_compute_sl_dat_mua_de_xuat',
        store=True,
        digits=(16, 3),
    )
    sl_dat_mua_chot = fields.Float(string='SL đặt mua chốt BCU', digits=(16, 3))
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua dựa theo MOQ NCC', digits=(16, 3))
    don_gia_mua = fields.Monetary(
        string='Đơn giá mua', currency_field='currency_id')
    gia_tri_mua_hang = fields.Monetary(
        string='Giá trị mua hàng',
        compute='_compute_b6_derived',
        store=True,
        currency_field='currency_id',
    )
    sl_ton_kho_cuoi_ky = fields.Float(
        string='Tồn kho cuối kỳ',
        compute='_compute_b6_derived',
        store=True,
        digits=(16, 3),
    )
    vt_loi_ton_lau = fields.Float(string='VT lỗi, tồn lâu ngày', digits=(16, 3))
    so_ngay_vong_quay_ton = fields.Float(
        string='Ngày vòng quay tồn kho',
        compute='_compute_b6_derived',
        store=True,
        digits=(16, 2),
    )
    don_gia_ton_kho_cuoi_ky = fields.Monetary(
        string='Đơn giá tồn cuối kỳ',
        compute='_compute_b6_derived',
        store=True,
        currency_field='currency_id',
    )
    gia_tri_ton_kho_cuoi_ky = fields.Monetary(
        string='Giá trị tồn kho cuối kỳ',
        compute='_compute_b6_derived',
        store=True,
        currency_field='currency_id',
    )

    ghi_chu = fields.Char(string='Ghi chú')

    @staticmethod
    def _count_months_with_can_dung(t0, t1, t2, t3):
        return sum(1 for qty in (t0, t1, t2, t3) if (qty or 0.0) > 0)

    def _tdd_bcu(self):
        """Tổng SL đi đường BCU — bước 6 tính theo số này, không dùng đi đường đơn vị."""
        self.ensure_one()
        monthly = (
            (self.ve_du_kien_bcu_t0 or 0.0)
            + (self.ve_du_kien_bcu_t1 or 0.0)
            + (self.ve_du_kien_bcu_t2 or 0.0)
            + (self.ve_du_kien_bcu_t3 or 0.0)
        )
        if monthly:
            return monthly
        return self.tong_ve_du_kien_bcu or 0.0

    @staticmethod
    def _sl_chot_from_de_xuat(sl_de_xuat):
        return 0.0 if (sl_de_xuat or 0.0) > 0 else -(sl_de_xuat or 0.0)

    def _sl_dat_mua_de_xuat_value(self):
        self.ensure_one()
        ton_dau = self.tong_ton_nvl_sl or 0.0
        tcd = self.tong_vt_can_dung or 0.0
        tdd = self._tdd_bcu()
        sl_du_tru = self.sl_du_tru_toi_thieu or 0.0
        return ton_dau - tcd + tdd - sl_du_tru

    @api.depends(
        'tong_ton_nvl_sl',
        'tong_vt_can_dung',
        'sl_du_tru_toi_thieu',
        'tong_ve_du_kien_bcu',
        've_du_kien_bcu_t0',
        've_du_kien_bcu_t1',
        've_du_kien_bcu_t2',
        've_du_kien_bcu_t3',
    )
    def _compute_sl_dat_mua_de_xuat(self):
        for rec in self:
            rec.sl_dat_mua_de_xuat = rec._sl_dat_mua_de_xuat_value()

    def _b6_derived_values(self):
        self.ensure_one()
        ton_dau = self.tong_ton_nvl_sl or 0.0
        tdd = self._tdd_bcu()
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
        'tong_ve_du_kien_bcu',
        've_du_kien_bcu_t0',
        've_du_kien_bcu_t1',
        've_du_kien_bcu_t2',
        've_du_kien_bcu_t3',
        'sl_can_mua_theo_moq',
        'don_gia_mua',
        'don_gia_ton_kho',
        'tong_sl_vt_can_dung_t0',
        'tong_sl_vt_can_dung_t1',
        'tong_sl_vt_can_dung_t2',
        'tong_sl_vt_can_dung_t3',
    )
    def _compute_b6_derived(self):
        for rec in self:
            derived = rec._b6_derived_values()
            rec.sl_ton_kho_cuoi_ky = derived['sl_ton_kho_cuoi_ky']
            rec.so_ngay_vong_quay_ton = derived['so_ngay_vong_quay_ton']
            rec.don_gia_ton_kho_cuoi_ky = derived['don_gia_ton_kho_cuoi_ky']
            rec.gia_tri_ton_kho_cuoi_ky = derived['gia_tri_ton_kho_cuoi_ky']
            rec.gia_tri_mua_hang = derived['gia_tri_mua_hang']

    @api.model
    def _apply_chot_from_bcu_di_duong(self, records):
        """Sau khi cập nhật đi đường BCU: tính lại chốt/moq theo công thức B5."""
        if not records:
            return
        ids, chots = [], []
        for rec in records:
            chot = rec._sl_chot_from_de_xuat(rec._sl_dat_mua_de_xuat_value())
            ids.append(rec.id)
            chots.append(chot)
        if not ids:
            return
        self.env.cr.execute("""
            UPDATE kh_dat_vat_tu_bcu AS b SET
                sl_dat_mua_chot = v.chot,
                sl_can_mua_theo_moq = v.chot,
                write_uid = %s,
                write_date = NOW() AT TIME ZONE 'UTC'
            FROM (
                SELECT unnest(%s::int[]) AS id,
                       unnest(%s::numeric[]) AS chot
            ) AS v
            WHERE b.id = v.id
        """, [self.env.uid, ids, chots])
        records.invalidate_recordset([
            'sl_dat_mua_chot', 'sl_can_mua_theo_moq', 'write_uid', 'write_date',
        ])

    @api.model
    def _format_qty(self, qty):
        return '{:,.3f}'.format(qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')

    def _log_tracked_changes(self, old):
        changes_by_period = {}
        for fname, static_label in _B6_TRACKED_FIELDS.items():
            if fname not in old:
                continue
            for rec in self:
                ov, nv = old[fname][rec.id], rec[fname]
                if abs((ov or 0.0) - (nv or 0.0)) <= 1e-9:
                    continue
                if not rec.period_id:
                    continue
                label = '%s — Mã NVL %s' % (static_label, rec.ma_sap or '')
                changes_by_period.setdefault(rec.period_id, []).append((
                    self._format_qty(ov),
                    self._format_qty(nv),
                    label,
                ))

        for period, changes in changes_by_period.items():
            if not changes:
                continue
            items = ''.join(
                "<li>"
                "<b class='o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold'>%s</b>"
                "<i class='o_TrackingValue_separator fa fa-long-arrow-right mx-1 text-600' role='img'></i>"
                "<b class='o-mail-Message-trackingNew me-1 fw-bold text-info'>%s</b>"
                "<span class='o-mail-Message-trackingField ms-1 fst-italic text-muted'>(%s)</span>"
                "</li>" % (escape(old_val), escape(new_val), escape(label))
                for old_val, new_val, label in changes
            )
            period.message_post(body=Markup("<ul>%s</ul>") % Markup(items))

    def write(self, vals):
        tracked = [fname for fname in _B6_TRACKED_FIELDS if fname in vals]
        if (
            not tracked
            or self.env.context.get('tracking_disable')
            or self.env.context.get('is_importing')
        ):
            return super().write(vals)

        old = {
            fname: {rec.id: rec[fname] for rec in self}
            for fname in tracked
        }
        res = super().write(vals)
        self._log_tracked_changes(old)
        return res
