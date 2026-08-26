# -*- coding: utf-8 -*-
from datetime import datetime

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_B5_TRACKED_FIELDS = {
    'sl_dat_mua_de_xuat': 'Đề xuất đặt mua',
    'sl_dat_mua_chot': 'Đặt mua chốt',
    'sl_can_mua_theo_moq': 'SL cần mua dựa theo MOQ NCC',
}

_B5_CAN_DUNG_TRACKED = {
    'tong_sl_vt_can_dung_t0': 'Cần dùng T0',
    'tong_sl_vt_can_dung_t1': 'Cần dùng T1',
    'tong_sl_vt_can_dung_t2': 'Cần dùng T2',
    'tong_sl_vt_can_dung_t3': 'Cần dùng T3',
}

_B5_QTY_FIELDS = (
    'tong_sl_vt_can_dung_t0', 'tong_sl_vt_can_dung_t1',
    'tong_sl_vt_can_dung_t2', 'tong_sl_vt_can_dung_t3',
)
_B5_DD_FIELDS = (
    'tong_hang_di_duong_sl_t0', 'tong_hang_di_duong_sl_t1',
    'tong_hang_di_duong_sl_t2', 'tong_hang_di_duong_sl_t3',
)

_MANUAL_RECOMPUTE_FIELDS = {'ma_sap', *_B5_QTY_FIELDS, *_B5_DD_FIELDS}

# Cột sinh lại khi đổi cần dùng / đi đường trên B5.
_B5_PLAN_OUTPUT_FIELDS = (
    'tong_vt_can_dung',
    'tong_hang_di_duong',
    'sl_du_tru_toi_thieu',
    'sl_dat_mua_de_xuat',
    'sl_dat_mua_chot',
    'sl_can_mua_theo_moq',
)

_B5_MANUAL_CAN_FIELDS = _B5_QTY_FIELDS
_B5_MANUAL_DD_FIELDS = _B5_DD_FIELDS


class KhDatVatTu(models.Model):
    _name = 'kh.dat.vat.tu'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Kế hoạch đặt vật tư'
    _order = 'is_manual desc, period_id, company_id, ma_sap, id'

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
    is_manual = fields.Boolean(
        string='Thêm tay',
        default=False,
        index=True,
        help='Dòng do bộ phận SX thêm trên B5, không sinh từ procedure.',
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

    tong_hang_di_duong_sl_t0 = fields.Float(string='Đi đường SL T0', digits=(16, 3))
    tong_hang_di_duong_sl_t1 = fields.Float(string='Đi đường SL T1', digits=(16, 3))
    tong_hang_di_duong_sl_t2 = fields.Float(string='Đi đường SL T2', digits=(16, 3))
    tong_hang_di_duong_sl_t3 = fields.Float(string='Đi đường SL T3', digits=(16, 3))
    tong_hang_di_duong_dg_t0 = fields.Monetary(
        string='Đi đường ĐG T0', currency_field='currency_id')
    tong_hang_di_duong_dg_t1 = fields.Monetary(
        string='Đi đường ĐG T1', currency_field='currency_id')
    tong_hang_di_duong_dg_t2 = fields.Monetary(
        string='Đi đường ĐG T2', currency_field='currency_id')
    tong_hang_di_duong_dg_t3 = fields.Monetary(
        string='Đi đường ĐG T3', currency_field='currency_id')
    tong_hang_di_duong_gt_t0 = fields.Monetary(
        string='Đi đường GT T0', currency_field='currency_id')
    tong_hang_di_duong_gt_t1 = fields.Monetary(
        string='Đi đường GT T1', currency_field='currency_id')
    tong_hang_di_duong_gt_t2 = fields.Monetary(
        string='Đi đường GT T2', currency_field='currency_id')
    tong_hang_di_duong_gt_t3 = fields.Monetary(
        string='Đi đường GT T3', currency_field='currency_id')
    tong_hang_di_duong = fields.Float(string='Tổng SL đi đường', digits=(16, 3))
    tong_gia_tri_di_duong = fields.Monetary(
        string='Tổng giá trị đi đường', currency_field='currency_id')

    sl_du_tru_toi_thieu = fields.Float(string='Dự trữ tối thiểu đơn vị', digits=(16, 3))
    sl_dat_mua_de_xuat = fields.Float(string='SL đặt mua đề xuất', digits=(16, 3))
    sl_dat_mua_chot = fields.Float(string='SL đặt mua chốt', digits=(16, 3))
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua dựa theo MOQ NCC', digits=(16, 3))
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

    _sql_constraints = [
        (
            'kh_dat_vat_tu_period_ma_uniq',
            'unique(period_id, ma_sap)',
            'Mã NVL đã tồn tại trên kế hoạch đặt vật tư của kỳ này.',
        ),
    ]

    # ------------------------------------------------------------------
    # Công thức B5 (khớp fn_ke_hoach_dat_vat_tu)
    # ------------------------------------------------------------------

    @staticmethod
    def _count_months_with_can_dung(t0, t1, t2, t3):
        return sum(1 for qty in (t0, t1, t2, t3) if (qty or 0.0) > 0)

    @staticmethod
    def _prev_month_key(period_month):
        text = (period_month or '').strip()
        if not text:
            return ''
        try:
            dt = datetime.strptime(text, '%m/%Y')
        except ValueError:
            return text
        if dt.month == 1:
            return '12/%d' % (dt.year - 1)
        return '%02d/%d' % (dt.month - 1, dt.year)

    @api.model
    def _sap_branch_sql(self, sx_company_code):
        code = (sx_company_code or '').strip().upper()
        if code == 'BNH':
            return "chi_nhanh LIKE '21%%'"
        if code == 'SSP':
            return "chi_nhanh LIKE '22%%'"
        return "chi_nhanh NOT LIKE '10%%'"

    @api.model
    def _load_sap_ton_kho_map(self, ma_codes, month_key, sx_company_code):
        """{ma_sap: {ton_dau, don_gia}} — cùng nguồn B4/B5 (md_sap_ton_kho)."""
        codes = sorted({(c or '').strip() for c in ma_codes if (c or '').strip()})
        if not codes or not month_key:
            return {}
        cr = self.env.cr
        cr.execute("SELECT to_regclass('public.md_sap_ton_kho')")
        if not cr.fetchone()[0]:
            return {}
        branch_filter = self._sap_branch_sql(sx_company_code)
        cr.execute(
            """
            WITH sap_rows AS (
                SELECT
                    TRIM(mtk.ma_hang) AS ma_hang,
                    mtk.chi_nhanh,
                    mtk.create_date,
                    mtk.id,
                    safe_sap_numeric(mtk.ton_cuoi) AS ton_cuoi,
                    safe_sap_numeric(mtk.ton_dau) AS ton_dau,
                    safe_sap_numeric(mtk.tien_ton_dau) AS tien_ton_dau
                FROM md_sap_ton_kho mtk
                WHERE TRIM(mtk.ma_hang) = ANY(%(codes)s)
                  AND fn_md_sap_ton_kho_month_key(
                          mtk.from_date, mtk.to_date, mtk.tu_ngay, mtk.den_ngay, mtk.create_date
                      ) = %(month_key)s
                  AND (
                      safe_sap_numeric(mtk.ton_cuoi) <> 0
                      OR safe_sap_numeric(mtk.ton_dau) <> 0
                      OR safe_sap_numeric(mtk.tien_ton_dau) <> 0
                  )
                  AND """
            + branch_filter
            + """
            ),
            latest AS (
                SELECT DISTINCT ON (ma_hang, chi_nhanh)
                    ma_hang, ton_cuoi, ton_dau, tien_ton_dau
                FROM sap_rows
                ORDER BY ma_hang, chi_nhanh, create_date DESC, id DESC
            )
            SELECT
                ma_hang,
                SUM(ton_cuoi) AS tdu,
                SUM(ton_dau) AS sl_dau,
                SUM(tien_ton_dau) AS ttdu
            FROM latest
            GROUP BY ma_hang
            """,
            {'codes': codes, 'month_key': month_key},
        )
        result = {}
        for ma_hang, tdu, sl_dau, ttdu in cr.fetchall():
            ton_dau = tdu or 0.0
            if sl_dau:
                don_gia = (ttdu or 0.0) / sl_dau
            else:
                don_gia = 0.0
            result[ma_hang] = {'ton_dau': ton_dau, 'don_gia': don_gia}
        return result

    @api.model
    def _load_di_duong_qty_map(self, company_id, ma_nvl, month_keys):
        """{month_key: so_luong} từ vat_tu_di_duong loại SX."""
        ma_nvl = (ma_nvl or '').strip()
        if not company_id or not ma_nvl or not month_keys:
            return {}
        rows = self.env['vat.tu.di.duong'].sudo().search([
            ('company_id', '=', company_id),
            ('ma_nvl', '=', ma_nvl),
            ('month_key', 'in', month_keys),
            ('loai', '=', 'don_vi'),
        ])
        return {row.month_key: row.so_luong or 0.0 for row in rows}

    def _b5_derived_values(self):
        """Công thức Excel: tồn cuối, vòng quay, đơn giá/giá trị tồn cuối."""
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

    @staticmethod
    def _calc_b5_plan(ton_dau, t0, t1, t2, t3, dd_t0, dd_t1, dd_t2, dd_t3, ngay_dt=20.0):
        """Công thức B5 thuần — khớp fn_ke_hoach_dat_vat_tu (procedure SQL)."""
        tcd = (t0 or 0.0) + (t1 or 0.0) + (t2 or 0.0) + (t3 or 0.0)
        tdd = (dd_t0 or 0.0) + (dd_t1 or 0.0) + (dd_t2 or 0.0) + (dd_t3 or 0.0)
        cd_t0 = t0 or 0.0
        ngay_dt = ngay_dt or 20.0
        sl_du_tru = (cd_t0 / 28.0) * ngay_dt if cd_t0 > 0 else 0.0
        ton_dau = ton_dau or 0.0
        sl_de_xuat = ton_dau - tcd + tdd - sl_du_tru
        sl_chot = 0.0 if sl_de_xuat > 0 else -sl_de_xuat
        return {
            'tong_vt_can_dung': tcd,
            'tong_hang_di_duong': tdd,
            'sl_du_tru_toi_thieu': sl_du_tru,
            'sl_dat_mua_de_xuat': sl_de_xuat,
            'sl_dat_mua_chot': sl_chot,
            'sl_can_mua_theo_moq': sl_chot,
        }

    def _m2o_id(self, fname, vals=None):
        """Trích id Many2one từ vals hoặc dòng hiện tại (tránh browse(recordset))."""
        vals = vals or {}
        if fname in vals:
            val = vals[fname]
            if not val:
                return False
            return val if isinstance(val, int) else val.id
        if len(self) == 1:
            val = self[fname]
            return val.id if val else False
        return False

    def _b5_ngay_du_tru(self, vals=None):
        """Số ngày dự trữ B5 của kỳ (mặc định 20)."""
        pid = self._m2o_id('period_id', vals)
        if not pid:
            return 20.0
        ngay = self.env['ke.hoach.vat.tu'].browse(pid).ngay_du_tru_b5
        return ngay or 20.0

    def _b5_field_from_vals(self, fname, vals):
        """Lấy giá trị field từ vals đang ghi, fallback sang dòng hiện tại."""
        if fname == 'period_id':
            return self._m2o_id(fname, vals) or False
        if fname in vals:
            return vals[fname]
        if len(self) == 1:
            return self[fname]
        return 0.0

    def _calc_b5_plan_from_vals(self, vals):
        """Tính lại các cột kế hoạch đặt mua từ dict đầu vào (+ dòng hiện tại nếu có)."""
        vals = dict(vals)
        return self._calc_b5_plan(
            self._b5_field_from_vals('tong_ton_nvl_sl', vals),
            *[self._b5_field_from_vals(f, vals) for f in _B5_QTY_FIELDS],
            *[self._b5_field_from_vals(f, vals) for f in _B5_DD_FIELDS],
            self._b5_ngay_du_tru(vals),
        )

    def _b5_plan_values(self):
        """Dự trữ / đề xuất / chốt / MOQ — wrapper đọc từ record."""
        self.ensure_one()
        return self._calc_b5_plan_from_vals({})

    def _apply_manual_totals(self, vals):
        """Gộp tổng cần dùng / đi đường và cột kế hoạch đặt mua vào vals."""
        vals = dict(vals)
        vals.update(self._calc_b5_plan_from_vals(vals))
        return vals

    def _b5_row_after_recompute(self, vals):
        """Gộp dòng hiện tại với vals đang ghi, rồi tính lại công thức B5."""
        self.ensure_one()
        row = {fname: self[fname] for fname in self._fields if fname != 'id'}
        row.update(vals)
        if vals.get('ma_sap') and self.is_manual:
            return self._manual_fill_from_ma_sap(row)
        return self._apply_manual_totals(row)

    def _manual_fill_from_ma_sap(self, vals):
        """Nạp MDM + SAP + đi đường cho dòng thêm tay."""
        ma_sap = (vals.get('ma_sap') or '').strip()
        if not ma_sap:
            return vals

        period_id = self._m2o_id('period_id', vals)
        period = self.env['ke.hoach.vat.tu'].browse(period_id)
        if not period:
            return vals

        company = period.company_sx_id
        if vals.get('company_id'):
            company = self.env['res.company'].browse(
                self._m2o_id('company_id', vals),
            )
        elif company:
            vals['company_id'] = company.id

        meta_map = self.env['ma.hang'].get_mdm_sap_meta_map([ma_sap])
        meta = meta_map.get(ma_sap, {})
        vals['ten_nvl'] = meta.get('ten_hang') or vals.get('ten_nvl') or ''

        mh = self.env['ma.hang'].search([('ma_sap', '=', ma_sap)], limit=1)
        if mh and mh.don_vi_tinh_id:
            vals['don_vi_tinh'] = mh.don_vi_tinh_id.id

        sx_code = (company.company_code or company.name or '') if company else ''
        month_key = self._prev_month_key(period.period_month)
        sap_map = self._load_sap_ton_kho_map([ma_sap], month_key, sx_code)
        sap = sap_map.get(ma_sap, {})
        vals['tong_ton_nvl_sl'] = sap.get('ton_dau', 0.0)
        vals['don_gia_ton_kho'] = sap.get('don_gia', 0.0)

        month_keys = period._get_horizon_months()
        dd_map = self._load_di_duong_qty_map(company.id, ma_sap, month_keys)
        for idx, month in enumerate(month_keys[:4]):
            vals.setdefault(_B5_DD_FIELDS[idx], dd_map.get(month, 0.0))

        for qty_key in _B5_QTY_FIELDS:
            vals.setdefault(qty_key, 0.0)

        vals.setdefault('don_gia_mua', 0.0)
        return self._apply_manual_totals(vals)

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

    @api.onchange('ma_sap')
    def _onchange_manual_ma_sap(self):
        for rec in self.filtered(lambda r: r.is_manual or not r.id):
            if not (rec.ma_sap or '').strip():
                continue
            vals = rec._manual_fill_from_ma_sap({
                'ma_sap': rec.ma_sap,
                'period_id': rec.period_id.id,
                'company_id': rec.company_id.id,
                'tong_sl_vt_can_dung_t0': rec.tong_sl_vt_can_dung_t0,
                'tong_sl_vt_can_dung_t1': rec.tong_sl_vt_can_dung_t1,
                'tong_sl_vt_can_dung_t2': rec.tong_sl_vt_can_dung_t2,
                'tong_sl_vt_can_dung_t3': rec.tong_sl_vt_can_dung_t3,
                'tong_hang_di_duong_sl_t0': rec.tong_hang_di_duong_sl_t0,
                'tong_hang_di_duong_sl_t1': rec.tong_hang_di_duong_sl_t1,
                'tong_hang_di_duong_sl_t2': rec.tong_hang_di_duong_sl_t2,
                'tong_hang_di_duong_sl_t3': rec.tong_hang_di_duong_sl_t3,
            })
            for fname, value in vals.items():
                if fname in rec._fields:
                    rec[fname] = value

    @api.onchange(
        'tong_sl_vt_can_dung_t0', 'tong_sl_vt_can_dung_t1',
        'tong_sl_vt_can_dung_t2', 'tong_sl_vt_can_dung_t3',
        'tong_hang_di_duong_sl_t0', 'tong_hang_di_duong_sl_t1',
        'tong_hang_di_duong_sl_t2', 'tong_hang_di_duong_sl_t3',
    )
    def _onchange_manual_qty_inputs(self):
        for rec in self:
            plan = rec._calc_b5_plan_from_vals({})
            for key in _B5_PLAN_OUTPUT_FIELDS:
                rec[key] = plan[key]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_is_manual'):
            res['is_manual'] = True
        return res

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            if vals.get('is_manual'):
                if not vals.get('period_id'):
                    raise UserError(_('Thiếu kỳ kế hoạch cho dòng thêm tay.'))
                ma_sap = (vals.get('ma_sap') or '').strip()
                if not ma_sap:
                    raise UserError(_('Vui lòng nhập Mã NVL.'))
                vals['ma_sap'] = ma_sap
                dup = self.search([
                    ('period_id', '=', vals['period_id']),
                    ('ma_sap', '=', ma_sap),
                ], limit=1)
                if dup:
                    raise ValidationError(
                        _('Mã NVL "%s" đã có trên kế hoạch đặt vật tư của kỳ này.')
                        % ma_sap
                    )
                vals = self._manual_fill_from_ma_sap(vals)
            prepared.append(vals)
        records = super().create(prepared)
        manual_created = records.filtered('is_manual')
        if manual_created and not self.env.context.get('tracking_disable'):
            manual_created._log_manual_action_table('create')
        return records

    def write(self, vals):
        vals = dict(vals)
        recompute_fields = _MANUAL_RECOMPUTE_FIELDS & set(vals)
        if (
            recompute_fields
            and not self.env.context.get('skip_b5_manual_recompute')
        ):
            if len(self) == 1:
                row = self._b5_row_after_recompute(vals)
                for key in _B5_PLAN_OUTPUT_FIELDS:
                    vals[key] = row[key]
            else:
                for rec in self:
                    rec_vals = dict(vals)
                    row = rec._b5_row_after_recompute(rec_vals)
                    for key in _B5_PLAN_OUTPUT_FIELDS:
                        rec_vals[key] = row[key]
                    super(KhDatVatTu, rec.with_context(
                        skip_b5_manual_recompute=True,
                    )).write(rec_vals)
                return True

        all_tracked = {**_B5_TRACKED_FIELDS, **_B5_CAN_DUNG_TRACKED}
        tracked = [fname for fname in all_tracked if fname in vals]
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
        self._log_b5_tracked_changes(old)
        return res

    def unlink(self):
        if self.env.context.get('force_b5_unlink'):
            return super().unlink()
        locked = self.filtered(lambda rec: not rec.is_manual)
        if locked:
            raise UserError(_('Chỉ được xóa dòng thêm tay trên kế hoạch đặt vật tư.'))
        manual = self.filtered('is_manual')
        if manual and not self.env.context.get('tracking_disable'):
            manual._log_manual_action_table('unlink')
        return super().unlink()

    @api.model
    def _format_b5_qty(self, qty):
        return '{:,.3f}'.format(qty or 0.0).replace(',', 'X').replace('.', ',').replace('X', '.')

    def _manual_tracking_values(self):
        self.ensure_one()
        return {
            'ma_sap': self.ma_sap or '',
            'ten_nvl': self.ten_nvl or '',
            'don_vi_tinh': self.don_vi_tinh.display_name if self.don_vi_tinh else '',
            'tong_ton_nvl_sl': self._format_b5_qty(self.tong_ton_nvl_sl),
            **{fname: self._format_b5_qty(self[fname]) for fname in _B5_MANUAL_CAN_FIELDS},
            **{fname: self._format_b5_qty(self[fname]) for fname in _B5_MANUAL_DD_FIELDS},
            'sl_dat_mua_de_xuat': self._format_b5_qty(self.sl_dat_mua_de_xuat),
            'sl_dat_mua_chot': self._format_b5_qty(self.sl_dat_mua_chot),
            'sl_can_mua_theo_moq': self._format_b5_qty(self.sl_can_mua_theo_moq),
        }

    @api.model
    def _b5_manual_month_labels(self, period):
        months = list(period._get_horizon_months()[:4]) if period else []
        while len(months) < 4:
            months.append('')
        can_labels = [
            _('Cần dùng %s') % (month or 'T%d' % idx)
            for idx, month in enumerate(months)
        ]
        dd_labels = [
            _('Đi đường %s') % (month or 'T%d' % idx)
            for idx, month in enumerate(months)
        ]
        return can_labels, dd_labels

    @api.model
    def _build_manual_action_table_html(self, title, lines, period, action='create'):
        can_labels, dd_labels = self._b5_manual_month_labels(period)

        def cell(value):
            value = escape(value)
            if action == 'unlink':
                return Markup("<del class='text-muted'>%s</del>") % value
            return value

        rows = Markup('').join(
            Markup(
                "<tr>"
                "<td>%(ma_sap)s</td>"
                "<td>%(ten_nvl)s</td>"
                "<td>%(don_vi_tinh)s</td>"
                "<td class='text-end'>%(tong_ton_nvl_sl)s</td>"
                "%(can_cells)s"
                "%(dd_cells)s"
                "<td class='text-end'>%(sl_dat_mua_de_xuat)s</td>"
                "<td class='text-end'>%(sl_dat_mua_chot)s</td>"
                "<td class='text-end'>%(sl_can_mua_theo_moq)s</td>"
                "</tr>"
            ) % {
                'ma_sap': cell(vals['ma_sap']),
                'ten_nvl': cell(vals['ten_nvl']),
                'don_vi_tinh': cell(vals['don_vi_tinh']),
                'tong_ton_nvl_sl': cell(vals['tong_ton_nvl_sl']),
                'can_cells': Markup('').join(
                    Markup("<td class='text-end'>%s</td>") % cell(vals[fname])
                    for fname in _B5_MANUAL_CAN_FIELDS
                ),
                'dd_cells': Markup('').join(
                    Markup("<td class='text-end'>%s</td>") % cell(vals[fname])
                    for fname in _B5_MANUAL_DD_FIELDS
                ),
                'sl_dat_mua_de_xuat': cell(vals['sl_dat_mua_de_xuat']),
                'sl_dat_mua_chot': cell(vals['sl_dat_mua_chot']),
                'sl_can_mua_theo_moq': cell(vals['sl_can_mua_theo_moq']),
            }
            for vals in lines
        )
        can_headers = Markup('').join(
            Markup("<th class='text-end'>%s</th>") % escape(label)
            for label in can_labels
        )
        dd_headers = Markup('').join(
            Markup("<th class='text-end'>%s</th>") % escape(label)
            for label in dd_labels
        )
        return Markup("""
            <p class="mb-2">%s</p>
            <div class="table-responsive">
                <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
                    <thead class="bg-light">
                        <tr>
                            <th>Mã NVL</th>
                            <th>Tên NVL</th>
                            <th>ĐVT</th>
                            <th class="text-end">Tồn NVL đầu kỳ</th>
                            %s
                            %s
                            <th class="text-end">Đề xuất đặt mua</th>
                            <th class="text-end">Đặt mua chốt</th>
                            <th class="text-end">SL cần mua theo MOQ</th>
                        </tr>
                    </thead>
                    <tbody>%s</tbody>
                </table>
            </div>
        """) % (Markup(title), can_headers, dd_headers, rows)

    def _log_manual_action_table(self, action='create'):
        period_lines = {}
        for rec in self.filtered(lambda r: r.period_id and r.is_manual):
            period_lines.setdefault(rec.period_id, []).append(rec._manual_tracking_values())

        for period, lines in period_lines.items():
            if action == 'create':
                title = (
                    "<span class='text-success'><i class='fa fa-plus-circle'></i> "
                    "<b>Đã thêm %d dòng kế hoạch đặt vật tư:</b></span>"
                ) % len(lines)
            else:
                title = (
                    "<span class='text-danger'><i class='fa fa-trash'></i> "
                    "<b>Đã xóa %d dòng kế hoạch đặt vật tư:</b></span>"
                ) % len(lines)
            period.message_post(
                body=self._build_manual_action_table_html(
                    title, lines, period, action=action,
                ),
            )

    def _can_dung_tracked_label(self, fname):
        """Nhãn log cần dùng theo tháng kỳ (T0..T3)."""
        idx_map = {
            'tong_sl_vt_can_dung_t0': 0,
            'tong_sl_vt_can_dung_t1': 1,
            'tong_sl_vt_can_dung_t2': 2,
            'tong_sl_vt_can_dung_t3': 3,
        }
        idx = idx_map.get(fname)
        if idx is None:
            return _B5_CAN_DUNG_TRACKED.get(fname, fname)
        period = self.period_id
        months = list(period._get_horizon_months()[:4]) if period else []
        month = months[idx] if idx < len(months) else ''
        return _('Cần dùng %s') % (month or 'T%d' % idx)

    def _log_b5_tracked_changes(self, old):
        """Ghi log lên chatter kỳ khi sửa cần dùng / đề xuất / chốt / MOQ trên B5."""
        all_tracked = {**_B5_TRACKED_FIELDS, **_B5_CAN_DUNG_TRACKED}
        changes_by_period = {}
        for fname in old:
            static_label = all_tracked.get(fname)
            for rec in self:
                ov, nv = old[fname][rec.id], rec[fname]
                if abs((ov or 0.0) - (nv or 0.0)) <= 1e-9:
                    continue
                if not rec.period_id:
                    continue
                if fname in _B5_CAN_DUNG_TRACKED:
                    label = '%s — Mã NVL %s' % (
                        rec._can_dung_tracked_label(fname), rec.ma_sap or '',
                    )
                else:
                    label = '%s — Mã NVL %s' % (static_label, rec.ma_sap or '')
                changes_by_period.setdefault(rec.period_id, []).append((
                    self._format_b5_qty(ov),
                    self._format_b5_qty(nv),
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
