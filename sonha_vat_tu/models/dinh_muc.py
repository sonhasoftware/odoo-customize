# -*- coding: utf-8 -*-
from odoo import api, fields, models

class DinhMuc(models.Model):
    _name = 'dinh.muc'
    _description = 'Định mức kỳ'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True)
    ma_sap = fields.Char(string='Mã', index=True)
    ten_sap = fields.Char(string='Tên SAP')
    ma_tp = fields.Char(string='Mã TP', index=True)
    ten_tp = fields.Char(string='Tên TP')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    sl_dinh_muc = fields.Float(
        string='Định mức', digits=(16, 3), readonly=True,
        help='Số lượng NVL / 1 SP theo nhánh BOM (sl_thuc_te từ bom_tinh_toan).',
    )
    bom_sale_id = fields.Many2one(
        'bom.sale', string='Loại Bom Sale', readonly=True, index=True,
        ondelete='set null',
        help='Loại Bom Sale (MDM) của NVL. Trống = chưa khai báo trên MDM, cần IT cập nhật.',
    )

    @api.model
    def _patch_bom_sale_for_ma_nvl(self, ma_nvl_code, bom_sale_id):
        """Đồng bộ bom_sale_id từ MDM sang mọi dòng định mức cùng mã NVL."""
        code = (ma_nvl_code or '').strip()
        if not code:
            return

        uid = self.env.uid
        self.env.cr.execute(
            """
            UPDATE dinh_muc
               SET bom_sale_id = %s,
                   write_uid = %s,
                   write_date = NOW() AT TIME ZONE 'UTC'
             WHERE TRIM(ma_nvl) = %s
            """,
            (bom_sale_id or None, uid, code),
        )
        if not self.env.cr.rowcount:
            return

        self.env.cr.execute(
            """
            SELECT id FROM dinh_muc WHERE TRIM(ma_nvl) = %s
            """,
            (code,),
        )
        dm_ids = [row[0] for row in self.env.cr.fetchall()]
        if dm_ids:
            self.browse(dm_ids).invalidate_recordset([
                'bom_sale_id', 'write_uid', 'write_date',
            ])

        self.env.cr.execute(
            """
            UPDATE du_lieu_tong_hop_vat_tu
               SET bom_sale_id = %s,
                   write_uid = %s,
                   write_date = NOW() AT TIME ZONE 'UTC'
             WHERE step_code = 'b2'
               AND source_model = 'dinh.muc'
               AND TRIM(ma_nvl) = %s
            """,
            (bom_sale_id or None, uid, code),
        )

    qty_kinh_doanh_t0 = fields.Float(string='KD T0', digits=(16, 2))
    qty_kinh_doanh_t1 = fields.Float(string='KD T1', digits=(16, 2))
    qty_kinh_doanh_t2 = fields.Float(string='KD T2', digits=(16, 2))
    qty_kinh_doanh_t3 = fields.Float(string='KD T3', digits=(16, 2))

    qty_san_xuat_t0 = fields.Float(string='SX T0', digits=(16, 2))
    qty_san_xuat_t1 = fields.Float(string='SX T1', digits=(16, 2))
    qty_san_xuat_t2 = fields.Float(string='SX T2', digits=(16, 2))
    qty_san_xuat_t3 = fields.Float(string='SX T3', digits=(16, 2))

    qty_chenh_lech_t0 = fields.Float(string='CL T0', digits=(16, 2))
    qty_chenh_lech_t1 = fields.Float(string='CL T1', digits=(16, 2))
    qty_chenh_lech_t2 = fields.Float(string='CL T2', digits=(16, 2))
    qty_chenh_lech_t3 = fields.Float(string='CL T3', digits=(16, 2))

    qty_t0 = fields.Float(string='Số lượng T0', digits=(16, 3))
    qty_t1 = fields.Float(string='Số lượng T1', digits=(16, 3))
    qty_t2 = fields.Float(string='Số lượng T2', digits=(16, 3))
    qty_t3 = fields.Float(string='Số lượng T3', digits=(16, 3))

    def init(self):
        super().init()
        # Backfill định mức cho dữ liệu B2 cũ (trước khi có cột sl_dinh_muc).
        self.env.cr.execute("""
            UPDATE dinh_muc dm
               SET sl_dinh_muc = sub.n,
                   write_date = NOW() AT TIME ZONE 'UTC'
              FROM (
                    SELECT dm2.id,
                           CASE
                               WHEN ABS(COALESCE(b1.qty_t0, 0)) > 1e-9
                               THEN ROUND((dm2.qty_t0 / b1.qty_t0)::NUMERIC, 3)
                               ELSE 0
                           END AS n
                      FROM dinh_muc dm2
                      JOIN ke_hoach_vat_tu_line b1
                        ON b1.period_id = dm2.period_id
                       AND b1.ma_sap = dm2.ma_sap
                     WHERE COALESCE(dm2.sl_dinh_muc, 0) = 0
                       AND COALESCE(dm2.qty_t0, 0) <> 0
                   ) sub
             WHERE dm.id = sub.id
        """)
        self.env.cr.execute("""
            UPDATE du_lieu_tong_hop_vat_tu dl
               SET sl_dinh_muc = d.sl_dinh_muc,
                   write_date = NOW() AT TIME ZONE 'UTC'
              FROM dinh_muc d
             WHERE dl.step_code = 'b2'
               AND dl.source_model = 'dinh.muc'
               AND dl.source_res_id = d.id
               AND COALESCE(dl.sl_dinh_muc, 0) = 0
               AND COALESCE(d.sl_dinh_muc, 0) <> 0
        """)
