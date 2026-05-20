# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BaoCaoTongQuanVatTu(models.Model):
    _name = 'bao.cao.tong.quan.vat.tu'
    _description = 'Báo cáo tổng quan vật tư'
    _auto = False
    _order = 'period_month desc, id desc'
    _rec_name = 'period_id'

    period_id = fields.Many2one('ke.hoach.vat.tu', string='Kỳ', readonly=True)
    code = fields.Char(string='Mã', readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', readonly=True)
    qty_kinh_doanh = fields.Float(string='Kinh doanh', digits=(16, 2), readonly=True)
    qty_san_xuat = fields.Float(string='Sản xuất', digits=(16, 2), readonly=True)
    tong_nvl = fields.Float(string='Tổng NVL', digits=(16, 3), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW bao_cao_tong_quan_vat_tu AS (
                WITH flat AS (
                    SELECT
                        period_id,
                        SUM(CASE WHEN step_code = 'kd' THEN COALESCE(qty, 0) ELSE 0 END) AS qty_kinh_doanh,
                        SUM(CASE WHEN step_code = 'sx' THEN COALESCE(qty, 0) ELSE 0 END) AS qty_san_xuat,
                        SUM(CASE
                            WHEN step_code = 'b3' THEN COALESCE(sl_dinh_muc, qty, 0)
                            ELSE 0
                        END) AS tong_nvl
                    FROM du_lieu_tong_hop_vat_tu
                    GROUP BY period_id
                )
                SELECT
                    p.id AS id,
                    p.id AS period_id,
                    p.code AS code,
                    p.period_month AS period_month,
                    p.company_id AS company_id,
                    COALESCE(flat.qty_kinh_doanh, 0) AS qty_kinh_doanh,
                    COALESCE(flat.qty_san_xuat, 0) AS qty_san_xuat,
                    COALESCE(flat.tong_nvl, 0) AS tong_nvl
                FROM ke_hoach_vat_tu p
                LEFT JOIN flat ON flat.period_id = p.id
            )
        """)
