# -*- coding: utf-8 -*-
from odoo import api, fields, models

REPORT_DMTB = 'dmtb'
REPORT_VTCD = 'vtcd'
REPORT_KH_DSX = 'khdsx'


class BaoCaoGhiChu(models.Model):
    _name = 'bao.cao.ghi.chu'
    _description = 'Ghi chú lưu báo cáo vật tư (persistent)'
    _order = 'report_type, period_key, scope_key, id'

    report_type = fields.Selection(
        [
            (REPORT_DMTB, 'Định mức vật tư trung bình'),
            (REPORT_VTCD, 'Vật tư cần đặt'),
            (REPORT_KH_DSX, 'Tổng hợp KH đặt sản xuất'),
        ],
        string='Loại báo cáo',
        required=True,
        index=True,
    )
    period_key = fields.Char(
        string='Khóa kỳ',
        required=True,
        index=True,
        help='Tháng kế hoạch + đơn vị SX (vd. 07/2026|BNH).',
    )
    scope_key = fields.Char(
        string='Khóa dòng',
        required=True,
        index=True,
        help='Định danh dòng trong báo cáo (mã NVL, công ty…).',
    )
    noi_dung = fields.Text(string='Ghi chú')

    _sql_constraints = [
        (
            'uniq_bao_cao_ghi_chu',
            'unique(report_type, period_key, scope_key)',
            'Đã có ghi chú cho dòng báo cáo này.',
        ),
    ]

    @api.model
    def period_key_from_periods(self, periods):
        """Khóa ổn định theo tháng + ĐV SX — không phụ thuộc mã file KHVT_00x."""
        if not periods:
            return ''
        months = {(p.period_month or '').strip() for p in periods if p.period_month}
        if len(months) != 1:
            return ','.join(str(p.id) for p in sorted(periods, key=lambda p: p.id))
        month = next(iter(months))
        sx_codes = sorted({
            (p.company_sx_id.company_code or p.company_sx_id.name or '').strip().upper()
            for p in periods if p.company_sx_id
        })
        if not sx_codes:
            return month
        return '%s|%s' % (month, '|'.join(sx_codes))

    @staticmethod
    def scope_key_dmtb(nhom_id, nguon_sl_sp, company_sx_id):
        return '%s|%s|%s' % (nhom_id or 0, nguon_sl_sp or '', company_sx_id or 0)

    @staticmethod
    def scope_key_vtcd(report_kind, ma_nvl):
        return '%s|%s' % (report_kind or '', (ma_nvl or '').strip())

    @staticmethod
    def scope_key_khdsx(company_sx_id, company_dat_id, nganh_hang):
        return '%s|%s|%s' % (
            company_sx_id or 0,
            company_dat_id or 0,
            (nganh_hang or '').strip(),
        )

    @api.model
    def load_map(self, report_type, period_key, scope_keys=None):
        if not period_key:
            return {}
        domain = [
            ('report_type', '=', report_type),
            ('period_key', '=', period_key),
        ]
        if scope_keys is not None:
            domain.append(('scope_key', 'in', list(scope_keys)))
        rows = self.sudo().search(domain)
        return {
            rec.scope_key: (rec.noi_dung or '')
            for rec in rows
        }

    @api.model
    def upsert_note(self, report_type, period_key, scope_key, noi_dung):
        if not period_key or not scope_key:
            return self.browse()
        text = (noi_dung or '').strip()
        domain = [
            ('report_type', '=', report_type),
            ('period_key', '=', period_key),
            ('scope_key', '=', scope_key),
        ]
        existing = self.sudo().search(domain, limit=1)
        if existing:
            existing.write({'noi_dung': text})
            return existing
        if not text:
            return self.browse()
        return self.sudo().create({
            'report_type': report_type,
            'period_key': period_key,
            'scope_key': scope_key,
            'noi_dung': text,
        })

    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute("SELECT to_regclass('public.dmtb_ghi_chu')")
        if not cr.fetchone()[0]:
            return
        cr.execute("SELECT to_regclass('public.bao_cao_ghi_chu')")
        if not cr.fetchone()[0]:
            return
        cr.execute(
            """
            INSERT INTO bao_cao_ghi_chu (
                report_type, period_key, scope_key, noi_dung,
                create_uid, create_date, write_uid, write_date
            )
            SELECT
                'dmtb',
                COALESCE(
                    NULLIF(TRIM(k.period_month), '') || '|' ||
                    UPPER(COALESCE(rc.company_code, rc.name, '')),
                    g.period_id::text
                ),
                g.nhom_linh_vuc || '|' || g.nguon_sl_sp || '|' || g.company_sx_id::text,
                g.noi_dung,
                g.create_uid, g.create_date, g.write_uid, g.write_date
            FROM dmtb_ghi_chu g
            JOIN ke_hoach_vat_tu k ON k.id = g.period_id
            LEFT JOIN res_company rc ON rc.id = g.company_sx_id
            WHERE COALESCE(TRIM(g.noi_dung), '') <> ''
            ON CONFLICT (report_type, period_key, scope_key) DO NOTHING
            """
        )
