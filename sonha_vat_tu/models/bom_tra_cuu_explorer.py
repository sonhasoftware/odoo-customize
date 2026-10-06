# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, models
from odoo.exceptions import UserError


class BomTraCuuExplorer(models.AbstractModel):
    """Tra cứu ngược: theo mã NVL → TP gốc dùng NVL + bảng định mức / vật tư cần."""

    _name = 'bom.tra.cuu.explorer'
    _description = 'Tra cứu BOM theo NVL'

    @api.model
    def _wizard_stub(self, period, thang_tu, thang_den):
        return self.env['tra.cuu.bom.wizard'].new({
            'period_id': period.id,
            'thang_tu': thang_tu,
            'thang_den': thang_den,
        })

    @api.model
    def get_period_info(self, period_id):
        period = self.env['ke.hoach.vat.tu'].browse(period_id)
        if not period.exists():
            raise UserError(_('Không tìm thấy kỳ.'))
        horizon = period._get_horizon_months() or []
        self.env.cr.execute(
            """
            SELECT TRIM(dm.ma_nvl) AS ma, MAX(NULLIF(TRIM(dm.ten_nvl), '')) AS ten
            FROM dinh_muc dm
            WHERE dm.period_id = %s
              AND dm.ma_nvl IS NOT NULL
              AND TRIM(dm.ma_nvl) <> ''
            GROUP BY TRIM(dm.ma_nvl)
            ORDER BY TRIM(dm.ma_nvl)
            """,
            (period_id,),
        )
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
    def _month_offsets(self, period, thang_tu, thang_den):
        return self.env['bom.cay.explorer']._month_offsets(
            period, thang_tu, thang_den,
        )

    @api.model
    def _build_tree_lines(self, rows):
        """Cây: gốc NVL (client) + danh sách TP gốc distinct."""
        by_tp = {}
        for row in rows:
            tp = row.get('ma_tp_goc') or ''
            if tp and tp not in by_tp:
                by_tp[tp] = row.get('ten_tp_goc') or ''
        lines = []
        for idx, (ma, ten) in enumerate(sorted(by_tp.items())):
            is_last = idx == len(by_tp) - 1
            lines.append({
                'prefix': '└──' if is_last else '├──',
                'loai': 'TP',
                'ma': ma,
                'ten': ten,
                'sl': '',
                'dim': False,
                'on_dm': True,
            })
        return lines

    @api.model
    def _detail_rows(self, rows, offsets):
        out = []
        for row in rows:
            months = {}
            for off in offsets:
                months[str(off)] = {
                    'qty_kh': row.get('qty_kh_t%d' % off) or 0.0,
                    'qty_nvl': row.get('qty_nvl_t%d' % off) or 0.0,
                }
            out.append({
                'don_vi_kd_code': row.get('don_vi_kd_code') or '',
                'ma_tp_goc': row.get('ma_tp_goc') or '',
                'ten_tp_goc': row.get('ten_tp_goc') or '',
                'ma_tp_cha': row.get('ma_tp_cha') or '',
                'ten_tp_cha': row.get('ten_tp_cha') or '',
                'ma_nvl': row.get('ma_con') or '',
                'ten_nvl': row.get('ten_con') or '',
                'sl_thuc_te': row.get('sl_thuc_te') or 0.0,
                'cap_bom': row.get('cap_bom') or 0,
                'months': months,
            })
        return out

    @api.model
    def _sum_totals(self, detail_rows, offsets):
        totals = {str(off): {'qty_kh': 0.0, 'qty_nvl': 0.0} for off in offsets}
        for row in detail_rows:
            for off in offsets:
                m = row['months'].get(str(off), {})
                totals[str(off)]['qty_kh'] += m.get('qty_kh') or 0.0
                totals[str(off)]['qty_nvl'] += m.get('qty_nvl') or 0.0
        return totals

    @api.model
    def load_explorer(self, period_id, ma_nvl, thang_tu, thang_den):
        ma_nvl = (ma_nvl or '').strip()
        if not ma_nvl:
            raise UserError(_('Chọn hoặc nhập mã NVL.'))
        period = self.env['ke.hoach.vat.tu'].browse(period_id)
        if not period.exists():
            raise UserError(_('Không tìm thấy kỳ.'))
        if not self.env['dinh.muc'].search_count([('period_id', '=', period.id)]):
            raise UserError(_(
                'Kỳ "%s" chưa có định mức (B2). Chạy sinh định mức trên kỳ trước.'
            ) % (period.display_name,))

        offsets, month_labels, mk_tu, mk_den = self._month_offsets(
            period, thang_tu, thang_den,
        )
        wiz = self._wizard_stub(period, thang_tu, thang_den)
        rows = wiz._fetch_rows_sql(ma_nvl=ma_nvl)
        if not rows:
            raise UserError(_(
                'Không có dòng định mức cho mã NVL %(ma)s trên kỳ %(ky)s.'
            ) % {'ma': ma_nvl, 'ky': period.display_name})

        ten_nvl = rows[0].get('ten_con') or ''
        detail = self._detail_rows(rows, offsets)
        totals = self._sum_totals(detail, offsets)

        visible_months = [
            {'offset': off, 'label': month_labels.get(off, 'T%d' % off)}
            for off in offsets
        ]
        tp_count = len({r['ma_tp_goc'] for r in detail if r.get('ma_tp_goc')})

        return {
            'ma_nvl': ma_nvl,
            'ten_nvl': ten_nvl,
            'range_label': '%s → %s' % (mk_tu, mk_den),
            'tree_lines': self._build_tree_lines(rows),
            'detail_table': detail,
            'month_totals': totals,
            'visible_months': visible_months,
            'stats': {
                'tp_count': tp_count,
                'line_count': len(detail),
            },
        }
