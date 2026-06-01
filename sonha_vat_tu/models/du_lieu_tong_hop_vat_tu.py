# -*- coding: utf-8 -*-
import os as _os

from psycopg2 import sql

from odoo import _, api, fields, models


class DuLieuTongHopVatTu(models.Model):
    """Bảng phẳng phục vụ báo cáo: đồng bộ từ B1–B5 qua trigger PostgreSQL.
    """
    _name = 'du.lieu.tong.hop.vat.tu'
    _description = 'Dữ liệu tổng hợp vật tư'
    _order = 'step_code, period_id, month_date, ma_sap, id'
    _rec_name = 'display_name'

    step_code = fields.Selection(
        [
            ('kd', 'Kế hoạch kinh doanh'),
            ('sx', 'Kế hoạch sản xuất'),
            ('b1', 'Kế hoạch vật tư'),
            ('b2', 'Định mức kỳ'),
            ('b3', 'Tính toán vật tư'),
            ('b4', 'Tổng hợp vật tư'),
            ('b5', 'Kế hoạch đặt vật tư'),
        ],
        string='Bước',
        index=True,
        readonly=True,
    )
    source_model = fields.Char(string='Model nguồn', readonly=True, index=True)
    source_res_id = fields.Integer(string='ID dòng nguồn', readonly=True, index=True)

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', index=True, readonly=True)
    period_company_id = fields.Many2one(
        'res.company', string='Đơn vị yêu cầu', index=True, readonly=True)
    period_code = fields.Char(string='Số chứng từ', index=True, readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', index=True, readonly=True)
    company_code = fields.Char(string='Mã đơn vị sản xuất', index=True, readonly=True)
    period_company_code = fields.Char(string='Mã đơn vị yêu cầu', index=True, readonly=True)
    month_key = fields.Char(string='Tháng', index=True, readonly=True)
    month_date = fields.Date(string='Tháng tính toán', index=True, readonly=True)
    ma_sap = fields.Char(string='Mã SAP', index=True, readonly=True)
    ma_vat_tu = fields.Char(string='Mã nguyên vật liệu', index=True, readonly=True)

    # --- --
    nganh_hang_id = fields.Many2one('nganh.hang', string='Ngành hàng', readonly=True)
    dong_hang_id = fields.Many2one('dong.hang', string='Dòng hàng', readonly=True)
    ma_hang_id = fields.Many2one('ma.hang', string='Mã hàng', readonly=True)

    qty = fields.Float(string='Số lượng (B1/B2/B3)', digits=(16, 4), readonly=True)
    note = fields.Char(string='Ghi chú (B1)', readonly=True)

    # --- --
    ma_tp = fields.Char(string='Mã thành phẩm', readonly=True)
    ten_tp = fields.Char(string='Tên thành phẩm', readonly=True)
    ten_sap = fields.Char(string='Tên SAP', readonly=True)
    ma_nvl = fields.Char(string='Mã NVL', readonly=True)
    ten_nvl = fields.Char(string='Tên NVL', readonly=True)
    ten_vat_tu = fields.Char(string='Tên vật tư', readonly=True)
    qty_kinh_doanh = fields.Float(string='Kinh doanh', digits=(16, 2), readonly=True)
    qty_san_xuat = fields.Float(string='Sản xuất', digits=(16, 2), readonly=True)
    qty_chenh_lech = fields.Float(string='Chênh lệch', digits=(16, 2), readonly=True)

    # --- B3 (+ chồng tên với B2 khi cùng bước không xảy ra) ---
    ma_effect = fields.Char(string='Mã effect', readonly=True)
    don_vi_tinh = fields.Many2one(
        'uom.uom',
        string='ĐVT',
        readonly=True,
    )
    do_day = fields.Float(string='Độ dày', digits=(16, 2), readonly=True)
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0), readonly=True)
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0), readonly=True)
    trong_luong_kg_tam = fields.Float(
        string='Trọng lượng kg/1 tấm', digits=(16, 8), readonly=True)
    sl_dinh_muc = fields.Float(
        string='SL định mức / 1 SP', digits=(16, 3), readonly=True)

    # --- --
    ma_dat_hang = fields.Char(string='Mã đặt hàng', readonly=True)
    chung_loai = fields.Char(string='Chủng loại', readonly=True)
    ma_cuon = fields.Char(string='Mã cuộn', readonly=True)
    ton_dau = fields.Float(string='Tồn đầu', digits=(16, 3), readonly=True)
    ve_du_kien = fields.Float(string='Vật tư đi đường', digits=(16, 3), readonly=True)
    vt_can_dung = fields.Float(string='VT cần dùng', digits=(16, 3), readonly=True)
    ton_cuoi = fields.Float(string='Tồn cuối', digits=(16, 3), readonly=True)
    so_luong_du_phong = fields.Float(string='SL dự phòng', digits=(16, 3), readonly=True)
    so_luong_thieu = fields.Float(string='SL thiếu', digits=(16, 3), readonly=True)
    so_luong_can_mua = fields.Float(string='SL cần mua', digits=(16, 3), readonly=True)
    ghi_chu = fields.Char(string='Ghi chú (B4/B5)', readonly=True)

    # --- --
    tong_ton_nvl_sl = fields.Float(string='Tổng tồn NVL', digits=(16, 3), readonly=True)
    tong_hang_di_duong_sl = fields.Float(string='Tổng hàng đi đường', digits=(16, 3), readonly=True)
    tong_sl_vt_can_dung = fields.Float(string='Tổng SL VT cần dùng', digits=(16, 3), readonly=True)
    sl_du_tru_toi_thieu = fields.Float(string='SL dự trữ tối thiểu', digits=(16, 3), readonly=True)
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua theo MOQ', digits=(16, 3), readonly=True)
    sl_dat_mua_de_xuat = fields.Float(string='SL đặt mua đề xuất', digits=(16, 3), readonly=True)
    sl_dat_mua_chot = fields.Float(string='SL đặt mua chốt', digits=(16, 3), readonly=True)
    sl_ton_kho = fields.Float(string='SL tồn kho', digits=(16, 3), readonly=True)
    so_ngay_vong_quay_ton = fields.Float(string='Ngày vòng quay tồn', digits=(16, 2), readonly=True)
    don_gia_ton_kho = fields.Float(string='Đơn giá tồn kho', digits=(16, 3), readonly=True)
    gia_tri_ton_kho = fields.Float(string='Giá trị tồn kho', digits=(16, 3), readonly=True)

    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('uniq_dlthvt_source',
         'unique(source_model, source_res_id)',
         'Mỗi dòng nguồn chỉ có một bản ghi tổng hợp.'),
    ]

    @api.depends('step_code', 'ma_sap', 'month_key', 'source_res_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s %s #%s' % (
                rec.step_code or '?',
                rec.ma_sap or '',
                rec.month_key or '',
                rec.source_res_id or 0,
            )

    @api.model
    def init(self):
        self._cr.execute(_read_sql_file())
        try:
            self._cr.execute(_read_sql_bom_file())
        except Exception:
            pass

    def action_rebuild_from_sources(self):
        self.env.cr.execute(_read_sql_file())
        self.env.cr.execute('DELETE FROM du_lieu_tong_hop_vat_tu')
        for tbl in _SOURCE_TABLES:
            self.env.cr.execute(
                sql.SQL('UPDATE {} SET id = id WHERE id IS NOT NULL').format(
                    sql.Identifier(tbl)
                )
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ'),
                'message': _('Đã làm mới dữ liệu bảng tổng hợp.'),
                'type': 'success',
                'sticky': False,
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SQL_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'du_lieu_tong_hop_vat_tu_triggers.sql',
)

_SQL_BOM_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'fn_bom_chuoi_cung_ung.sql',
)

_SOURCE_TABLES = (
    'ke_hoach_kinh_doanh',
    'ke_hoach_san_xuat',
    'ke_hoach_vat_tu_line',
    'dinh_muc',
    'tinh_toan_vat_tu',
    'tong_hop_vat_tu',
    'kh_dat_vat_tu',
)


def _read_sql_file():
    """Đọc file data/du_lieu_tong_hop_vat_tu_triggers.sql."""
    with open(_SQL_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def _read_sql_bom_file():
    """Đọc file data/fn_bom_chuoi_cung_ung.sql."""
    with open(_SQL_BOM_PATH, 'r', encoding='utf-8') as f:
        return f.read()
