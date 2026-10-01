# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import UserError


class BomCayExplorer(models.AbstractModel):
    """API xem cây bom_tinh_toan + bảng NVL định mức kỳ (không qua fn B3)."""

    _name = 'bom.cay.explorer'
    _description = 'Xem cây BOM'

    @api.model
    def _chi_nhanh_filter(self, company_sx):
        if not company_sx:
            return '', []
        code = (company_sx.company_code or '').strip().upper()
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
            return ' AND b.chi_nhanh LIKE %s', [val]
        return ' AND TRIM(b.chi_nhanh) = %s', [str(val)]

    @api.model
    def _chi_nhanh_label(self, company_sx):
        if not company_sx:
            return _('chưa cấu hình ĐV SX')
        code = (company_sx.company_code or '').strip().upper()
        mapping = {
            'BNH': '21xx',
            'SSP': '22xx',
            'NAN': '3000',
            'TM2': '4000',
            'TM': '5000',
        }
        branch = mapping.get(code)
        name = company_sx.display_name
        if branch:
            return '%s (%s)' % (name, branch)
        return name or code or '?'

    @api.model
    def _fetch_bom_rows(self, ma_tp_goc, cn_sql, cn_params):
        query = """
            SELECT
                TRIM(b.ma_tp_goc) AS ma_tp_goc,
                b.ten_tp_goc,
                NULLIF(TRIM(b.ma_tp_cha), '') AS ma_tp_cha,
                TRIM(b.ma_con) AS ma_con,
                b.ten_con,
                b.loai_vat_tu,
                b.cap_bom,
                b.sl_thuc_te,
                NULLIF(TRIM(b.chi_nhanh), '') AS chi_nhanh
            FROM bom_tinh_toan b
            WHERE TRIM(b.ma_tp_goc) = %s
              {cn_sql}
            ORDER BY b.cap_bom, b.ma_tp_cha, b.ma_con, b.chi_nhanh
        """.format(cn_sql=cn_sql)
        self.env.cr.execute(query, [ma_tp_goc.strip()] + cn_params)
        return self.env.cr.dictfetchall()

    @api.model
    def _ma_hang_set(self, codes):
        codes = [c for c in codes if c]
        if not codes:
            return set()
        self.env.cr.execute(
            "SELECT TRIM(ma_sap) FROM ma_hang WHERE TRIM(ma_sap) = ANY(%s)",
            (codes,),
        )
        return {r[0] for r in self.env.cr.fetchall() if r[0]}

    @api.model
    def _build_children_index(self, rows):
        by_parent = defaultdict(list)
        nvl_codes = set()
        ten_goc = rows[0].get('ten_tp_goc') if rows else ''
        cn_set = set()
        for row in rows:
            parent = row.get('ma_tp_cha') or ''
            by_parent[parent].append(row)
            if row.get('loai_vat_tu') == 'NVL':
                nvl_codes.add(row['ma_con'])
            if row.get('chi_nhanh'):
                cn_set.add(row['chi_nhanh'])
        for parent in by_parent:
            by_parent[parent].sort(
                key=lambda r: (r.get('cap_bom') or 0, r['ma_con']),
            )
        return by_parent, nvl_codes, ten_goc, ', '.join(sorted(cn_set)[:5])

    @api.model
    def _fmt_qty(self, sl):
        if sl is None:
            return '?'
        val = float(sl)
        if abs(val - round(val)) < 1e-9:
            return str(int(round(val)))
        return ('%.6f' % val).rstrip('0').rstrip('.')

    @api.model
    def _node_label(self, row, ma_hang, cap_bom):
        loai = row.get('loai_vat_tu') or '?'
        ma = row['ma_con']
        ten = (row.get('ten_con') or '').strip()
        qty = self._fmt_qty(row.get('sl_thuc_te'))
        if cap_bom == 1 and loai == 'BTP':
            qty_part = '× %s / SP' % qty
        else:
            qty_part = '× %s' % qty
        parts = ['[%s]' % loai, ma]
        if ten:
            parts.append(ten)
        parts.append(qty_part)
        line = ' '.join(parts)
        if loai == 'NVL' and ma not in ma_hang:
            line += '  ← không có trong ma_hang'
        return line

    @api.model
    def _bom_children(self, by_parent, root, parent_code):
        if parent_code is None:
            seen = set()
            merged = []
            for key in (root, ''):
                for row in by_parent.get(key, []):
                    ma = row['ma_con']
                    if ma == root or ma in seen:
                        continue
                    seen.add(ma)
                    merged.append(row)
            return merged
        return by_parent.get(parent_code, [])

    @api.model
    def _build_nested_tree(self, by_parent, ma_hang, root, parent_code=None):
        nodes = []
        children = self._bom_children(by_parent, root, parent_code)
        for row in children:
            cap = int(row.get('cap_bom') or 1)
            loai = row.get('loai_vat_tu') or ''
            ma = row['ma_con']
            has_kids = bool(by_parent.get(ma))
            nodes.append({
                'id': '%s-%s' % (parent_code or root, ma),
                'loai': loai,
                'ma_con': ma,
                'ten_con': (row.get('ten_con') or '').strip(),
                'sl_label': self._fmt_qty(row.get('sl_thuc_te')),
                'cap_bom': cap,
                'warn_ma_hang': loai == 'NVL' and ma not in ma_hang,
                'children': (
                    self._build_nested_tree(by_parent, ma_hang, root, ma)
                    if loai == 'BTP' and has_kids else []
                ),
            })
        return nodes

    @api.model
    def _tree_lines(self, nodes, nvl_on_dm=None, prefix=''):
        nvl_on_dm = nvl_on_dm or set()
        lines = []
        for idx, node in enumerate(nodes):
            is_last = idx == len(nodes) - 1
            loai = node['loai']
            ma = node['ma_con']
            on_dm = loai == 'NVL' and ma in nvl_on_dm
            dim = loai == 'BTP' or (
                node['warn_ma_hang'] and not on_dm
            )
            lines.append({
                'prefix': prefix + ('└── ' if is_last else '├── '),
                'loai': loai,
                'ma': ma,
                'ten': node['ten_con'],
                'sl': node['sl_label'],
                'warn': node['warn_ma_hang'],
                'on_dm': on_dm,
                'dim': dim,
            })
            if node['children']:
                lines.extend(self._tree_lines(
                    node['children'], nvl_on_dm,
                    prefix + ('    ' if is_last else '│   '),
                ))
        return lines

    @api.model
    def _merge_nvl_table(self, rows, offsets):
        """Gộp theo mã NVL (bỏ tách ĐV KD trên UI)."""
        merged = {}
        order = []
        for row in rows:
            key = row.get('ma_nvl') or ''
            if key not in merged:
                merged[key] = {
                    'ma_nvl': key,
                    'ten_nvl': row.get('ten_nvl') or '',
                    'sl_thuc_te': row.get('sl_thuc_te') or 0,
                    'months': {
                        str(off): {'qty_kh': 0, 'qty_nvl': 0} for off in offsets
                    },
                }
                order.append(key)
            entry = merged[key]
            if not entry['ten_nvl'] and row.get('ten_nvl'):
                entry['ten_nvl'] = row['ten_nvl']
            if not entry['sl_thuc_te'] and row.get('sl_thuc_te'):
                entry['sl_thuc_te'] = row['sl_thuc_te']
            for off in offsets:
                sk = str(off)
                m = row.get('months', {}).get(sk, {})
                entry['months'][sk]['qty_kh'] += m.get('qty_kh') or 0
                entry['months'][sk]['qty_nvl'] += m.get('qty_nvl') or 0
        return [merged[k] for k in order]

    @api.model
    def _flatten_tree(self, by_parent, ma_hang, root, parent_code=None, depth=0):
        lines = []
        children = self._bom_children(by_parent, root, parent_code)
        for idx, row in enumerate(children):
            is_last = idx == len(children) - 1
            cap = int(row.get('cap_bom') or 1)
            lines.append({
                'depth': depth,
                'is_last': is_last,
                'branch': '└──' if is_last else '├──',
                'label': self._node_label(row, ma_hang, cap),
                'loai_vat_tu': row.get('loai_vat_tu') or '',
                'ma_con': row['ma_con'],
                'ma_tp_cha': row.get('ma_tp_cha') or '',
                'cap_bom': cap,
            })
            if row.get('loai_vat_tu') == 'BTP':
                lines.extend(
                    self._flatten_tree(
                        by_parent, ma_hang, root,
                        parent_code=row['ma_con'],
                        depth=depth + 1,
                    )
                )
        return lines

    @api.model
    def _month_offsets(self, period, thang_tu, thang_den):
        Kh = self.env['ke.hoach.vat.tu']
        wizard = self.env['tra.cuu.bom.wizard']
        mk_tu = wizard._parse_month_key(thang_tu)
        mk_den = wizard._parse_month_key(thang_den)
        d_from = Kh.month_start_from_key(mk_tu)
        d_to = Kh.month_end_from_key(mk_den)
        Kh.validate_report_month_range(d_from, d_to)
        horizon = period._get_horizon_months()
        if not horizon:
            raise UserError(_('Kỳ không có horizon tháng.'))
        selected = set(Kh.iter_calendar_months(d_from, d_to))
        offsets = [i for i, mk in enumerate(horizon) if mk in selected]
        if not offsets:
            raise UserError(_(
                'Khoảng %s → %s không giao horizon kỳ.'
            ) % (mk_tu, mk_den))
        labels = {i: horizon[i] for i in range(4) if i < len(horizon)}
        return offsets, labels, mk_tu, mk_den

    @api.model
    def _fetch_nvl_table(self, period_id, ma_tp_goc, offsets):
        """NVL trên dinh_muc kỳ (phần mua) — có định mức + KH tháng."""
        query = """
            SELECT
                COALESCE(NULLIF(TRIM(dv.company_code), ''), dv.name) AS don_vi_kd_code,
                TRIM(dm.ma_nvl) AS ma_nvl,
                NULLIF(TRIM(dm.ten_nvl), '') AS ten_nvl,
                NULLIF(TRIM(dm.ma_tp), '') AS ma_tp_cha,
                NULLIF(TRIM(dm.ten_tp), '') AS ten_tp_cha,
                CASE
                    WHEN dm.co_sl_dinh_muc_override
                        THEN COALESCE(dm.sl_dinh_muc_thay_doi, 0)
                    ELSE COALESCE(dm.sl_dinh_muc, 0)
                END AS sl_thuc_te,
                CASE
                    WHEN eff.sl <> 0 THEN COALESCE(dm.qty_t0, 0) / eff.sl
                    ELSE COALESCE(b1.qty_t0, 0)
                END AS qty_kh_t0,
                CASE
                    WHEN eff.sl <> 0 THEN COALESCE(dm.qty_t1, 0) / eff.sl
                    ELSE COALESCE(b1.qty_t1, 0)
                END AS qty_kh_t1,
                CASE
                    WHEN eff.sl <> 0 THEN COALESCE(dm.qty_t2, 0) / eff.sl
                    ELSE COALESCE(b1.qty_t2, 0)
                END AS qty_kh_t2,
                CASE
                    WHEN eff.sl <> 0 THEN COALESCE(dm.qty_t3, 0) / eff.sl
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
                END AS sl
            ) eff
            LEFT JOIN LATERAL (
                SELECT kh.qty_t0, kh.qty_t1, kh.qty_t2, kh.qty_t3
                FROM ke_hoach_vat_tu_line kh
                WHERE kh.period_id = dm.period_id
                  AND kh.company_id = dm.company_id
                  AND TRIM(kh.ma_sap) = TRIM(dm.ma_sap)
                  AND (
                      eff.sl = 0
                      OR ABS(
                          COALESCE(kh.qty_t0, 0)
                          - COALESCE(dm.qty_t0, 0) / NULLIF(eff.sl, 0)
                      ) < 0.001
                  )
                ORDER BY kh.sequence, kh.id
                LIMIT 1
            ) b1 ON TRUE
            WHERE dm.period_id = %s
              AND TRIM(dm.ma_sap) = %s
              AND dm.company_id IS NOT NULL
            ORDER BY dm.ma_tp, dm.ma_nvl, dv.company_code
        """
        self.env.cr.execute(query, [period_id, ma_tp_goc.strip()])
        rows = self.env.cr.dictfetchall()
        month_keys = ['qty_kh_t%d', 'qty_nvl_t%d']
        out = []
        for row in rows:
            item = {
                'don_vi_kd_code': row.get('don_vi_kd_code') or '',
                'ma_nvl': row.get('ma_nvl') or '',
                'ten_nvl': row.get('ten_nvl') or '',
                'ma_tp_cha': row.get('ma_tp_cha') or '',
                'ten_tp_cha': row.get('ten_tp_cha') or '',
                'sl_thuc_te': row.get('sl_thuc_te') or 0,
                'months': {},
            }
            for off in offsets:
                item['months'][str(off)] = {
                    'label_kh': month_keys[0] % off,
                    'qty_kh': row.get('qty_kh_t%d' % off) or 0,
                    'qty_nvl': row.get('qty_nvl_t%d' % off) or 0,
                }
            out.append(item)
        return out

    @api.model
    def get_period_info(self, period_id):
        period = self.env['ke.hoach.vat.tu'].browse(period_id)
        if not period.exists():
            raise UserError(_('Không tìm thấy kỳ.'))
        horizon = period._get_horizon_months() or []
        self.env.cr.execute("""
            SELECT DISTINCT TRIM(k.ma_sap) AS ma, MAX(k.ten_hang) AS ten
            FROM ke_hoach_vat_tu_line k
            WHERE k.period_id = %s AND k.ma_sap IS NOT NULL AND TRIM(k.ma_sap) <> ''
            GROUP BY TRIM(k.ma_sap)
            ORDER BY TRIM(k.ma_sap)
        """, (period_id,))
        ma_list = [
            {'ma': r['ma'], 'ten': r['ten'] or ''}
            for r in self.env.cr.dictfetchall()
        ]
        sx = period.company_sx_id
        return {
            'period_id': period.id,
            'period_name': period.display_name,
            'horizon': horizon,
            'thang_tu': horizon[0] if horizon else '',
            'thang_den': horizon[-1] if horizon else '',
            'company_sx': sx.display_name if sx else '',
            'ma_list': ma_list,
        }

    @api.model
    def load_explorer(self, period_id, ma_tp_goc, thang_tu, thang_den):
        ma_tp_goc = (ma_tp_goc or '').strip()
        if not ma_tp_goc:
            raise UserError(_('Chọn hoặc nhập mã TP gốc.'))
        period = self.env['ke.hoach.vat.tu'].browse(period_id)
        if not period.exists():
            raise UserError(_('Không tìm thấy kỳ.'))
        offsets, month_labels, mk_tu, mk_den = self._month_offsets(
            period, thang_tu, thang_den,
        )
        cn_sql, cn_params = self._chi_nhanh_filter(period.company_sx_id)
        rows = self._fetch_bom_rows(ma_tp_goc, cn_sql, cn_params)
        if not rows:
            cn_label = self._chi_nhanh_label(period.company_sx_id)
            raise UserError(_(
                'Không có BOM tính toán (bảng bom_tinh_toan) cho thành phẩm gốc %(ma)s '
                'với chi nhánh sản xuất %(cn)s.\n\n'
                'Gợi ý: kiểm tra đồng bộ BOM từ SAP, mã TP gốc đúng kỳ, '
                'và chi_nhanh khớp ĐV SX (vd. TM → 5000).'
            ) % {'ma': ma_tp_goc, 'cn': cn_label})

        by_parent, nvl_codes, ten_goc, cn_label = self._build_children_index(rows)
        ma_hang = self._ma_hang_set(list(nvl_codes))
        tree_children = self._build_nested_tree(by_parent, ma_hang, ma_tp_goc)
        nvl_raw = self._fetch_nvl_table(period_id, ma_tp_goc, offsets)
        nvl_table = self._merge_nvl_table(nvl_raw, offsets)
        nvl_on_dm = {r['ma_nvl'] for r in nvl_table if r.get('ma_nvl')}

        visible_months = [
            {'offset': off, 'label': month_labels.get(off, 'T%d' % off)}
            for off in offsets
        ]

        return {
            'ma_tp_goc': ma_tp_goc,
            'ten_tp_goc': ten_goc or '',
            'chi_nhanh': cn_label,
            'range_label': '%s → %s' % (mk_tu, mk_den),
            'tree_lines': self._tree_lines(tree_children, nvl_on_dm),
            'nvl_table': nvl_table,
            'visible_months': visible_months,
            'stats': {
                'nvl_on_tree': len(nvl_codes),
                'nvl_in_ma_hang': len(nvl_codes & ma_hang),
                'nvl_on_dm': len(nvl_table),
            },
        }
