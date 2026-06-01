# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BaoCaoTongQuanVatTu(models.Model):
    _name = 'bao.cao.tong.quan.vat.tu'
    _description = 'Báo cáo tổng quan vật tư'
    _auto = False
    _order = 'company_id, period_month desc, code, ma_nvl'
    _rec_name = 'period_id'

    period_id = fields.Many2one('ke.hoach.vat.tu', string='Kỳ', readonly=True)
    code = fields.Char(string='Số chứng từ', readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', readonly=True)
    company_id = fields.Many2one('res.company', string='Đơn vị', readonly=True)
    ma_nvl = fields.Char(string='Mã NVL', readonly=True)
    ten_nvl = fields.Char(string='Tên NVL', readonly=True)
    qty_kinh_doanh = fields.Float(string='Kinh doanh', digits=(16, 2), readonly=True)
    qty_san_xuat = fields.Float(string='Sản xuất', digits=(16, 2), readonly=True)
    qty_chenh_lech = fields.Float(string='Chênh lệch', digits=(16, 2), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW bao_cao_tong_quan_vat_tu AS (
                WITH flat AS (
                    SELECT
                        period_id,
                        company_id,
                        period_code,
                        period_month,
                        month_key,
                        month_date,
                        ma_nvl,
                        MAX(ten_nvl) AS ten_nvl,
                        SUM(COALESCE(qty_kinh_doanh, 0)) AS qty_kinh_doanh,
                        SUM(COALESCE(qty_san_xuat, 0)) AS qty_san_xuat,
                        SUM(COALESCE(qty_chenh_lech, 0)) AS qty_chenh_lech
                    FROM du_lieu_tong_hop_vat_tu
                    WHERE step_code = 'b2'
                      AND ma_nvl IS NOT NULL
                    GROUP BY
                        period_id, company_id, period_code, period_month, month_key, month_date, ma_nvl
                )
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY
                            flat.company_id,
                            flat.period_month DESC,
                            flat.period_code,
                            flat.month_date,
                            flat.ma_nvl
                    ) AS id,
                    flat.period_id AS period_id,
                    flat.period_code AS code,
                    flat.period_month AS period_month,
                    flat.company_id AS company_id,
                    flat.ma_nvl AS ma_nvl,
                    flat.ten_nvl AS ten_nvl,
                    COALESCE(flat.qty_kinh_doanh, 0) AS qty_kinh_doanh,
                    COALESCE(flat.qty_san_xuat, 0) AS qty_san_xuat,
                    COALESCE(flat.qty_chenh_lech, 0) AS qty_chenh_lech
                FROM flat
            )
        """)
