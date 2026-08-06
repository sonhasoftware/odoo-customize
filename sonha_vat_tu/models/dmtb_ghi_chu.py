# -*- coding: utf-8 -*-
from odoo import fields, models


class DmtbGhiChu(models.Model):
    _name = 'dmtb.ghi.chu'
    _description = 'Ghi chú báo cáo định mức vật tư trung bình'
    _order = 'period_id, company_sx_id, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', required=True, ondelete='cascade', index=True)
    nhom_linh_vuc = fields.Selection(
        [
            ('innox', 'Innox'),
            ('nhua', 'Nhựa'),
        ],
        string='Nhóm',
        required=True,
        index=True,
    )
    nguon_sl_sp = fields.Selection(
        [
            ('khkd', 'Kế hoạch kinh doanh'),
            ('khsx', 'Kế hoạch sản xuất'),
        ],
        string='Nguồn',
        required=True,
        index=True,
    )
    company_sx_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', required=True, index=True)
    noi_dung = fields.Text(string='Ghi chú')

    _sql_constraints = [
        (
            'uniq_dmtb_ghi_chu_key',
            'unique(period_id, nhom_linh_vuc, nguon_sl_sp, company_sx_id)',
            'Đã có ghi chú cho công ty / kỳ / nhóm / nguồn này.',
        ),
    ]

    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'dmtb_ghi_chu' AND column_name = 'nhom_bao_cao_id'
            """
        )
        if not cr.fetchone():
            return
        cr.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'dmtb_ghi_chu' AND column_name = 'nhom_linh_vuc'
            """
        )
        if not cr.fetchone():
            cr.execute(
                "ALTER TABLE dmtb_ghi_chu ADD COLUMN nhom_linh_vuc VARCHAR"
            )
            cr.execute(
                """
                UPDATE dmtb_ghi_chu g
                SET nhom_linh_vuc = CASE
                    WHEN lower(COALESCE(n.name, '')) LIKE '%nhựa%'
                      OR lower(COALESCE(n.name, '')) LIKE '%nhua%' THEN 'nhua'
                    ELSE 'innox'
                END
                FROM dmtb_nhom_bao_cao n
                WHERE g.nhom_bao_cao_id = n.id
                """
            )
            cr.execute(
                """
                UPDATE dmtb_ghi_chu
                SET nhom_linh_vuc = 'innox'
                WHERE nhom_linh_vuc IS NULL
                """
            )
        cr.execute(
            "ALTER TABLE dmtb_ghi_chu DROP CONSTRAINT IF EXISTS uniq_dmtb_ghi_chu_key"
        )
        cr.execute(
            "ALTER TABLE dmtb_ghi_chu DROP COLUMN IF EXISTS nhom_bao_cao_id CASCADE"
        )

    def _upsert_note(self, period, nhom_linh_vuc, nguon, company, noi_dung):
        domain = [
            ('period_id', '=', period.id),
            ('nhom_linh_vuc', '=', nhom_linh_vuc),
            ('nguon_sl_sp', '=', nguon),
            ('company_sx_id', '=', company.id),
        ]
        existing = self.search(domain, limit=1)
        text = (noi_dung or '').strip()
        if existing:
            existing.write({'noi_dung': text})
            return existing
        if not text:
            return self.browse()
        return self.create({
            'period_id': period.id,
            'nhom_linh_vuc': nhom_linh_vuc,
            'nguon_sl_sp': nguon,
            'company_sx_id': company.id,
            'noi_dung': text,
        })
