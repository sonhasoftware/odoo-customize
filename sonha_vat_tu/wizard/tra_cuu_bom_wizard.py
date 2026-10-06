# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_MONTH_RE = re.compile(r'^(\d{1,2})\s*/\s*(\d{4})$')


class TraCuuBomWizard(models.TransientModel):
    _name = 'tra.cuu.bom.wizard'
    _description = 'Tra cứu BOM / chi tiết tính toán vật tư'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu',
        string='Kế hoạch vật tư',
        required=True,
        domain="[('state', 'in', ('tinh_toan', 'tong_hop', 'dat_hang', 'bcu_tong_hop', 'phe_duyet'))]",
    )
    thang_tu = fields.Char(string='Từ tháng', required=True, help='Định dạng MM/YYYY, ví dụ 09/2026')
    thang_den = fields.Char(string='Đến tháng', required=True, help='Định dạng MM/YYYY')

    @api.model
    def _parse_month_key(self, text):
        raw = (text or '').strip()
        m = _MONTH_RE.match(raw)
        if not m:
            raise UserError(_('Tháng "%s" không hợp lệ. Dùng định dạng MM/YYYY (vd. 09/2026).') % (raw or '—'))
        month, year = int(m.group(1)), int(m.group(2))
        if month < 1 or month > 12:
            raise UserError(_('Tháng phải từ 01 đến 12.'))
        return '%02d/%d' % (month, year)

    @api.onchange('period_id')
    def _onchange_period_id(self):
        if not self.period_id:
            return
        months = self.period_id._get_horizon_months()
        if months:
            self.thang_tu = months[0]
            self.thang_den = months[-1]

    def _visible_month_offsets(self):
        self.ensure_one()
        period = self.period_id
        Kh = self.env['ke.hoach.vat.tu']
        mk_tu = self._parse_month_key(self.thang_tu)
        mk_den = self._parse_month_key(self.thang_den)
        d_from = Kh.month_start_from_key(mk_tu)
        d_to = Kh.month_end_from_key(mk_den)
        Kh.validate_report_month_range(d_from, d_to)

        horizon = period._get_horizon_months()
        if not horizon:
            raise UserError(_('Kỳ không có horizon tháng.'))

        selected = set(Kh.iter_calendar_months(d_from, d_to))
        offsets = [idx for idx, mk in enumerate(horizon) if mk in selected]
        if not offsets:
            raise UserError(_(
                'Khoảng tháng %s → %s không giao với horizon kỳ (%s).'
            ) % (mk_tu, mk_den, ', '.join(horizon)))
        return offsets, mk_tu, mk_den, horizon

    def _bom_chi_nhanh_sql(self):
        """Lọc bom_tinh_toan theo ĐV SX — khớp fn_sinh_dinh_muc."""
        sx = self.period_id.company_sx_id
        if not sx:
            return '', []
        code = (sx.company_code or '').strip().upper()
        mapping = {
            'BNH': ('LIKE', '21%'),
            'SSP': ('LIKE', '22%'),
            'NAN': ('=', '3000'),
            'TM2': ('=', '4000'),
            'TM': ('=', '5000'),
        }
        mode, val = mapping.get(code, (None, None))
        if not mode:
            return '', []
        if mode == 'LIKE':
            return ' AND b.chi_nhanh LIKE %s', [str(val)]
        return ' AND TRIM(b.chi_nhanh) = %s', [str(val)]

    def _fetch_rows_sql(self, ma_nvl=None):
        """Chỉ dòng NVL trên định mức kỳ (dinh_muc) + NVL nhập thẳng B1."""
        self.ensure_one()
        period_id = self.period_id.id
        ma_nvl = (ma_nvl or '').strip()
        dm_nvl_sql = ' AND TRIM(dm.ma_nvl) = %s' if ma_nvl else ''
        b1_nvl_sql = ' WHERE TRIM(d.ma_sap) = %s' if ma_nvl else ''
        bom_cn_sql, bom_cn_params = self._bom_chi_nhanh_sql()

        query = """
            WITH b1_direct AS (
                SELECT
                    b1.company_id,
                    TRIM(b1.ma_sap) AS ma_sap,
                    b1.ma_hang,
                    b1.ten_hang,
                    COALESCE(b1.qty_t0, 0) AS qty_t0,
                    COALESCE(b1.qty_t1, 0) AS qty_t1,
                    COALESCE(b1.qty_t2, 0) AS qty_t2,
                    COALESCE(b1.qty_t3, 0) AS qty_t3,
                    mh.ten_hang AS ten_nvl
                FROM ke_hoach_vat_tu_line b1
                INNER JOIN ma_hang mh ON TRIM(mh.ma_sap) = TRIM(b1.ma_sap)
                WHERE b1.period_id = %s
                  AND b1.company_id IS NOT NULL
                  AND b1.ma_sap IS NOT NULL
                  AND TRIM(b1.ma_sap) <> ''
                  AND NOT EXISTS (
                      SELECT 1
                      FROM dinh_muc dm
                      WHERE dm.period_id = b1.period_id
                        AND dm.company_id = b1.company_id
                        AND TRIM(dm.ma_sap) = TRIM(b1.ma_sap)
                  )
            ),
            bom_meta AS (
                SELECT DISTINCT ON (dm.id)
                    dm.id AS dm_id,
                    b.cap_bom,
                    TRIM(b.chi_nhanh) AS chi_nhanh
                FROM dinh_muc dm
                JOIN bom_tinh_toan b
                    ON TRIM(b.ma_tp_goc) = TRIM(dm.ma_sap)
                   AND TRIM(b.ma_con) = TRIM(dm.ma_nvl)
                   {bom_cn_sql}
                WHERE dm.period_id = %s
                ORDER BY
                    dm.id,
                    CASE
                        WHEN dm.ma_tp IS NOT NULL AND TRIM(dm.ma_tp) <> ''
                             AND TRIM(b.ma_tp_cha) = TRIM(dm.ma_tp) THEN 0
                        ELSE 1
                    END,
                    b.cap_bom DESC NULLS LAST,
                    b.chi_nhanh
            ),
            detail AS (
                SELECT
                    COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name) AS don_vi_kd_code,
                    TRIM(dm.ma_sap) AS ma_tp_goc,
                    NULLIF(TRIM(COALESCE(
                        NULLIF(TRIM(dm.ten_sap), ''),
                        NULLIF(TRIM(b1.ten_hang), '')
                    )), '') AS ten_tp_goc,
                    NULLIF(TRIM(dm.ma_tp), '') AS ma_tp_cha,
                    NULLIF(TRIM(dm.ten_tp), '') AS ten_tp_cha,
                    TRIM(dm.ma_nvl) AS ma_con,
                    NULLIF(TRIM(dm.ten_nvl), '') AS ten_con,
                    bom_meta.cap_bom,
                    NULLIF(TRIM(bom_meta.chi_nhanh), '') AS chi_nhanh,
                    eff.sl_thuc_te,
                    NULLIF(TRIM(b1.ma_hang), '') AS ma_hang,
                    CASE
                        WHEN eff.sl_thuc_te <> 0 THEN COALESCE(dm.qty_t0, 0) / eff.sl_thuc_te
                        ELSE COALESCE(b1.qty_t0, 0)
                    END AS qty_kh_t0,
                    CASE
                        WHEN eff.sl_thuc_te <> 0 THEN COALESCE(dm.qty_t1, 0) / eff.sl_thuc_te
                        ELSE COALESCE(b1.qty_t1, 0)
                    END AS qty_kh_t1,
                    CASE
                        WHEN eff.sl_thuc_te <> 0 THEN COALESCE(dm.qty_t2, 0) / eff.sl_thuc_te
                        ELSE COALESCE(b1.qty_t2, 0)
                    END AS qty_kh_t2,
                    CASE
                        WHEN eff.sl_thuc_te <> 0 THEN COALESCE(dm.qty_t3, 0) / eff.sl_thuc_te
                        ELSE COALESCE(b1.qty_t3, 0)
                    END AS qty_kh_t3,
                    COALESCE(dm.qty_t0, 0) AS qty_nvl_t0,
                    COALESCE(dm.qty_t1, 0) AS qty_nvl_t1,
                    COALESCE(dm.qty_t2, 0) AS qty_nvl_t2,
                    COALESCE(dm.qty_t3, 0) AS qty_nvl_t3
                FROM dinh_muc dm
                JOIN res_company dv ON dv.id = dm.company_id
                CROSS JOIN LATERAL (
                    SELECT CASE
                        WHEN dm.co_sl_dinh_muc_override
                            THEN COALESCE(dm.sl_dinh_muc_thay_doi, 0)
                        ELSE COALESCE(dm.sl_dinh_muc, 0)
                    END AS sl_thuc_te
                ) eff
                LEFT JOIN LATERAL (
                    SELECT
                        kh.ma_hang,
                        kh.ten_hang,
                        kh.qty_t0,
                        kh.qty_t1,
                        kh.qty_t2,
                        kh.qty_t3
                    FROM ke_hoach_vat_tu_line kh
                    WHERE kh.period_id = dm.period_id
                      AND kh.company_id = dm.company_id
                      AND TRIM(kh.ma_sap) = TRIM(dm.ma_sap)
                      AND (
                          eff.sl_thuc_te = 0
                          OR ABS(
                              COALESCE(kh.qty_t0, 0)
                              - COALESCE(dm.qty_t0, 0) / NULLIF(eff.sl_thuc_te, 0)
                          ) < 0.001
                      )
                    ORDER BY kh.sequence, kh.id
                    LIMIT 1
                ) b1 ON TRUE
                LEFT JOIN bom_meta ON bom_meta.dm_id = dm.id
                WHERE dm.period_id = %s
                  AND dm.company_id IS NOT NULL
                  {dm_nvl_sql}

                UNION ALL

                SELECT
                    COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name) AS don_vi_kd_code,
                    d.ma_sap AS ma_tp_goc,
                    NULLIF(TRIM(COALESCE(d.ten_hang, d.ten_nvl)), '') AS ten_tp_goc,
                    NULL::VARCHAR AS ma_tp_cha,
                    NULL::VARCHAR AS ten_tp_cha,
                    d.ma_sap AS ma_con,
                    NULLIF(TRIM(d.ten_nvl), '') AS ten_con,
                    NULL::INTEGER AS cap_bom,
                    NULL::VARCHAR AS chi_nhanh,
                    1.0 AS sl_thuc_te,
                    NULLIF(TRIM(d.ma_hang), '') AS ma_hang,
                    d.qty_t0 AS qty_kh_t0,
                    d.qty_t1 AS qty_kh_t1,
                    d.qty_t2 AS qty_kh_t2,
                    d.qty_t3 AS qty_kh_t3,
                    d.qty_t0 AS qty_nvl_t0,
                    d.qty_t1 AS qty_nvl_t1,
                    d.qty_t2 AS qty_nvl_t2,
                    d.qty_t3 AS qty_nvl_t3
                FROM b1_direct d
                JOIN res_company dv ON dv.id = d.company_id
                {b1_nvl_sql}
            )
            SELECT *
            FROM detail
            ORDER BY ma_tp_goc, cap_bom NULLS LAST, ma_tp_cha, ma_con, don_vi_kd_code
        """.format(
            bom_cn_sql=bom_cn_sql,
            dm_nvl_sql=dm_nvl_sql,
            b1_nvl_sql=b1_nvl_sql,
        )
        params = [period_id] + bom_cn_params + [period_id, period_id]
        if ma_nvl:
            params.append(ma_nvl)
            params.append(ma_nvl)
        self.env.cr.execute(query, params)
        return self.env.cr.dictfetchall()

    def _action_context(self, offsets, horizon):
        self.ensure_one()
        ctx = {
            'create': False,
            'edit': False,
            'delete': False,
            'bom_tra_period_id': self.period_id.id,
        }
        for idx in range(4):
            ctx['bom_tra_show_t%d' % idx] = idx in offsets
            if idx < len(horizon):
                ctx['bom_tra_label_t%d' % idx] = horizon[idx]
        return ctx

    def action_search(self):
        self.ensure_one()
        period = self.period_id
        if not self.env['dinh.muc'].search_count([('period_id', '=', period.id)]):
            raise UserError(_(
                'Kỳ "%s" chưa có định mức (B2). '
                'Chạy sinh định mức trên kỳ trước.'
            ) % (period.display_name,))

        offsets, mk_tu, mk_den, horizon = self._visible_month_offsets()
        rows = self._fetch_rows_sql()
        if not rows:
            raise UserError(_(
                'Kỳ "%s" không có dòng định mức / BOM để tra cứu.'
            ) % (period.display_name,))

        Line = self.env['tra.cuu.bom.line']
        Line.search([('wizard_id', '=', self.id)]).unlink()

        line_vals = []
        for row in rows:
            line_vals.append({
                'wizard_id': self.id,
                'don_vi_kd_code': row.get('don_vi_kd_code') or '',
                'ma_tp_goc': row.get('ma_tp_goc') or '',
                'ten_tp_goc': row.get('ten_tp_goc') or '',
                'ma_tp_cha': row.get('ma_tp_cha') or '',
                'ten_tp_cha': row.get('ten_tp_cha') or '',
                'ma_con': row.get('ma_con') or '',
                'ten_con': row.get('ten_con') or '',
                'cap_bom': row.get('cap_bom') or 0,
                'chi_nhanh': row.get('chi_nhanh') or '',
                'sl_thuc_te': row.get('sl_thuc_te') or 0.0,
                'ma_hang': row.get('ma_hang') or '',
                'qty_kh_t0': row.get('qty_kh_t0') or 0.0,
                'qty_kh_t1': row.get('qty_kh_t1') or 0.0,
                'qty_kh_t2': row.get('qty_kh_t2') or 0.0,
                'qty_kh_t3': row.get('qty_kh_t3') or 0.0,
                'qty_nvl_t0': row.get('qty_nvl_t0') or 0.0,
                'qty_nvl_t1': row.get('qty_nvl_t1') or 0.0,
                'qty_nvl_t2': row.get('qty_nvl_t2') or 0.0,
                'qty_nvl_t3': row.get('qty_nvl_t3') or 0.0,
            })
        Line.create(line_vals)

        ctx = self._action_context(offsets, horizon)
        title = _(
            'Tra cứu BOM — %(code)s (%(from)s → %(to)s)'
        ) % {
            'code': period.code or period.display_name,
            'from': mk_tu,
            'to': mk_den,
        }
        tree_view = self.env.ref('sonha_vat_tu.view_tra_cuu_bom_line_tree')
        search_view = self.env.ref('sonha_vat_tu.view_tra_cuu_bom_line_search')
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'tra.cuu.bom.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', self.id)],
            'context': ctx,
            'target': 'current',
            'views': [(tree_view.id, 'tree')],
            'search_view_id': search_view.id,
        }
