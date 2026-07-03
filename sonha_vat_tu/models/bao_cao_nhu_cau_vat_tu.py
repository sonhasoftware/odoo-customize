# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BaoCaoNhuCauVatTu(models.Model):
    _name = 'bao.cao.nhu.cau.vat.tu'
    _description = 'Báo cáo nhu cầu vật tư'
    _auto = False
    _order = 'company_id, ma_nvl'
    _rec_name = 'ma_nvl'

    period_id = fields.Many2one('ke.hoach.vat.tu', string='Kỳ', readonly=True)
    code = fields.Char(string='Số chứng từ', readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', readonly=True)
    period_start_date = fields.Date(string='Tháng bắt đầu (date)', readonly=True)
    period_end_date = fields.Date(string='Tháng kết thúc kỳ', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng', readonly=True,
        help='Đơn vị kinh doanh có kế hoạch KD (SHI, TM1…).',
    )
    company_sx_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', readonly=True,
    )
    company_code = fields.Char(string='Mã đơn vị đặt hàng', readonly=True)
    ma_nvl = fields.Char(string='Mã vật tư', readonly=True)
    ma_sap = fields.Char(string='Mã SAP', readonly=True)
    ma_effect = fields.Char(string='Mã effect', readonly=True)
    ma_cuon = fields.Char(string='Mã cuộn', readonly=True)
    ten_nvl = fields.Char(string='Tên vật tư', readonly=True)
    chung_loai = fields.Char(string='Chủng loại', readonly=True)
    don_vi_tinh = fields.Many2one('mdm.dvt', string='Đơn vị tính', readonly=True)
    so_luong_t0 = fields.Float(string='T0', digits=(16, 3), readonly=True)
    so_luong_t1 = fields.Float(string='T1', digits=(16, 3), readonly=True)
    so_luong_t2 = fields.Float(string='T2', digits=(16, 3), readonly=True)
    so_luong_t3 = fields.Float(string='T3', digits=(16, 3), readonly=True)
    tong_so_luong = fields.Float(
        string='Tổng SL vật tư cần dùng', digits=(16, 3), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW bao_cao_nhu_cau_vat_tu AS (
                WITH b4_kd AS (
                    SELECT
                        dl.*,
                        COALESCE(dl.ma_nvl, dl.ma_vat_tu, dl.ma_sap) AS ma_nvl_key
                    FROM du_lieu_tong_hop_vat_tu dl
                    WHERE dl.step_code = 'b4'
                      AND dl.period_company_id IS NOT NULL
                      AND COALESCE(dl.ma_nvl, dl.ma_vat_tu, dl.ma_sap) IS NOT NULL
                ),
                grouped AS (
                    SELECT
                        MIN(b4.id) AS id,
                        b4.period_id,
                        b4.period_code,
                        b4.period_month,
                        TO_DATE(b4.period_month, 'MM/YYYY') AS period_start_date,
                        (TO_DATE(b4.period_month, 'MM/YYYY') + INTERVAL '3 month')::date AS period_end_date,
                        b4.period_company_id AS company_id,
                        b4.company_id AS company_sx_id,
                        b4.ma_nvl_key,
                        MAX(COALESCE(b4.ten_nvl, b4.ten_vat_tu, b4.ten_sap)) AS ten_nvl,
                        MAX(b4.chung_loai) AS chung_loai,
                        MAX(b4.don_vi_tinh) AS don_vi_tinh,
                        SUM(CASE
                            WHEN b4.month_key = TO_CHAR(
                                TO_DATE(b4.period_month, 'MM/YYYY'), 'MM/YYYY')
                            THEN COALESCE(b4.vt_can_dung, 0) ELSE 0
                        END) AS so_luong_t0,
                        SUM(CASE
                            WHEN b4.month_key = TO_CHAR(
                                TO_DATE(b4.period_month, 'MM/YYYY') + INTERVAL '1 month', 'MM/YYYY')
                            THEN COALESCE(b4.vt_can_dung, 0) ELSE 0
                        END) AS so_luong_t1,
                        SUM(CASE
                            WHEN b4.month_key = TO_CHAR(
                                TO_DATE(b4.period_month, 'MM/YYYY') + INTERVAL '2 month', 'MM/YYYY')
                            THEN COALESCE(b4.vt_can_dung, 0) ELSE 0
                        END) AS so_luong_t2,
                        SUM(CASE
                            WHEN b4.month_key = TO_CHAR(
                                TO_DATE(b4.period_month, 'MM/YYYY') + INTERVAL '3 month', 'MM/YYYY')
                            THEN COALESCE(b4.vt_can_dung, 0) ELSE 0
                        END) AS so_luong_t3
                    FROM b4_kd b4
                    GROUP BY
                        b4.period_id,
                        b4.period_code,
                        b4.period_month,
                        b4.period_company_id,
                        b4.company_id,
                        b4.ma_nvl_key
                )
                SELECT
                    g.id,
                    g.period_id,
                    g.period_code AS code,
                    g.period_month,
                    g.period_start_date,
                    g.period_end_date,
                    g.company_id,
                    g.company_sx_id,
                    rc.company_code,
                    g.ma_nvl_key AS ma_nvl,
                    g.ma_nvl_key AS ma_sap,
                    kd.ma_hang AS ma_effect,
                    kd.ma_hang AS ma_cuon,
                    g.ten_nvl,
                    g.chung_loai,
                    g.don_vi_tinh,
                    g.so_luong_t0,
                    g.so_luong_t1,
                    g.so_luong_t2,
                    g.so_luong_t3,
                    COALESCE(g.so_luong_t0, 0) + COALESCE(g.so_luong_t1, 0)
                        + COALESCE(g.so_luong_t2, 0) + COALESCE(g.so_luong_t3, 0) AS tong_so_luong
                FROM grouped g
                LEFT JOIN res_company rc ON rc.id = g.company_id
                LEFT JOIN LATERAL (
                    SELECT kd_inner.ma_hang
                    FROM dinh_muc dm
                    JOIN ke_hoach_kinh_doanh kd_inner
                      ON kd_inner.period_id = dm.period_id
                     AND kd_inner.ma_sap = dm.ma_sap
                     AND kd_inner.company_id = g.company_id
                    WHERE dm.period_id = g.period_id
                      AND dm.ma_nvl = g.ma_nvl_key
                    ORDER BY kd_inner.id
                    LIMIT 1
                ) kd ON TRUE
            )
        """)
