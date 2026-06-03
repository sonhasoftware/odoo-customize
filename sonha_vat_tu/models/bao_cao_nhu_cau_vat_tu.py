# -*- coding: utf-8 -*-
from odoo import fields, models, tools


class BaoCaoNhuCauVatTu(models.Model):
    _name = 'bao.cao.nhu.cau.vat.tu'
    _description = 'Báo cáo nhu cầu vật tư'
    _auto = False
    _order = 'company_id, month_date, ma_nvl'
    _rec_name = 'ma_nvl'

    period_id = fields.Many2one('ke.hoach.vat.tu', string='Kỳ', readonly=True)
    code = fields.Char(string='Số chứng từ', readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', readonly=True)
    company_id = fields.Many2one('res.company', string='Đơn vị', readonly=True)
    company_code = fields.Char(string='Mã đơn vị', readonly=True)
    month_key = fields.Char(string='Tháng', readonly=True)
    month_date = fields.Date(string='Tháng tính toán', readonly=True)
    ma_nvl = fields.Char(string='Mã vật tư', readonly=True)
    ten_nvl = fields.Char(string='Tên vật tư', readonly=True)
    chung_loai = fields.Char(string='Chủng loại', readonly=True)
    don_vi_tinh = fields.Many2one('mdm.dvt', string='Đơn vị tính', readonly=True)
    so_luong_vat_tu_can_dung = fields.Float(
        string='Số lượng vật tư cần dùng', digits=(16, 3), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW bao_cao_nhu_cau_vat_tu AS (
                SELECT
                    id,
                    period_id,
                    period_code AS code,
                    period_month,
                    period_company_id AS company_id,
                    period_company_code AS company_code,
                    month_key,
                    month_date,
                    COALESCE(ma_nvl, ma_vat_tu, ma_sap) AS ma_nvl,
                    COALESCE(ten_nvl, ten_vat_tu, ten_sap) AS ten_nvl,
                    chung_loai,
                    don_vi_tinh,
                    COALESCE(vt_can_dung, 0) AS so_luong_vat_tu_can_dung
                FROM du_lieu_tong_hop_vat_tu
                WHERE step_code = 'b4'
                  AND COALESCE(ma_nvl, ma_vat_tu, ma_sap) IS NOT NULL
            )
        """)
