# -*- coding: utf-8 -*-
import os as _os

from odoo import api, fields, models


class DuLieuTongHopVatTu(models.Model):
    """Bảng phẳng phục vụ báo cáo: đồng bộ từ B1–B7 qua trigger PostgreSQL.
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
            ('b6', 'Kế hoạch đặt vật tư BCU'),
            ('b7', 'Phê duyệt kế hoạch vật tư'),
        ],
        string='Bước',
        index=True,
        readonly=True,
    )
    source_model = fields.Char(string='Model nguồn', readonly=True, index=True)
    source_res_id = fields.Integer(string='ID dòng nguồn', readonly=True, index=True)

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True, readonly=True)
    owner_company_id = fields.Many2one(
        'res.company', string='Đơn vị lập kế hoạch', index=True, readonly=True,
        help='Đơn vị của user tạo kỳ kế hoạch vật tư (vd. SSP → KHVT_SSP_001). Dùng phân quyền.',
    )
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True, readonly=True,
        help='B3/B4/B5/B6: đơn vị sản xuất. B7: đơn vị đặt hàng (BNH, SSP…).',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        related='company_id.currency_id',
        readonly=True,
    )
    period_company_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng', index=True, readonly=True,
        help='Đơn vị kinh doanh có kế hoạch KD (SHI, TM1…). B3/B4 chi tiết theo đơn vị này.')
    period_code = fields.Char(string='Số chứng từ', index=True, readonly=True)
    period_month = fields.Char(string='Tháng bắt đầu', index=True, readonly=True)
    company_code = fields.Char(string='Mã đơn vị sản xuất', index=True, readonly=True)
    period_company_code = fields.Char(string='Mã đơn vị đặt hàng', index=True, readonly=True)
    month_key = fields.Char(string='Tháng', index=True, readonly=True)
    month_date = fields.Date(string='Tháng tính toán', index=True, readonly=True)
    ma_sap = fields.Char(string='Mã', index=True, readonly=True)
    ma_vat_tu = fields.Char(string='Mã nguyên vật liệu', index=True, readonly=True)

    # --- --
    nganh_hang = fields.Char(string='Ngành hàng', readonly=True)
    ten_hang = fields.Char(string='Tên hàng', readonly=True)
    ma_hang = fields.Char(string='Mã hàng', readonly=True)

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

    # --- B3 ---
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT', readonly=True)
    do_day = fields.Float(string='Độ dày', digits=(16, 2), readonly=True)
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0), readonly=True)
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0), readonly=True)
    trong_luong_kg_tam = fields.Float(
        string='Trọng lượng kg/1 tấm', digits=(16, 8), readonly=True)
    sl_dinh_muc = fields.Float(
        string='SL định mức / 1 SP', digits=(16, 3), readonly=True,
        help='B2: định mức gốc theo nhánh BOM.',
    )
    sl_dinh_muc_thay_doi = fields.Float(
        string='Định mức thay đổi', digits=(16, 3), readonly=True,
    )
    sl_dinh_muc_ap_dung = fields.Float(
        string='Định mức áp dụng', digits=(16, 3), readonly=True,
        help='B2: định mức thay đổi nếu có, ngược lại lấy định mức gốc.',
    )

    # --- --
    ma_dat_hang = fields.Char(string='Mã đặt hàng', readonly=True)
    chung_loai = fields.Char(string='Chủng loại', readonly=True)
    ton_dau = fields.Float(string='Tồn đầu', digits=(16, 3), readonly=True)
    ve_du_kien_don_vi = fields.Float(
        string='Vật tư đi đường đơn vị', digits=(16, 3), readonly=True)
    ve_du_kien_don_gia = fields.Monetary(
        string='Đi đường đơn giá (B4)',
        currency_field='currency_id',
        readonly=True,
    )
    ve_du_kien_gia_tri = fields.Monetary(
        string='Đi đường giá trị (B4)',
        currency_field='currency_id',
        readonly=True,
    )
    vt_can_dung = fields.Float(string='VT cần dùng', digits=(16, 3), readonly=True)
    ton_cuoi = fields.Float(string='Tồn cuối', digits=(16, 3), readonly=True)
    so_luong_du_phong = fields.Float(string='SL dự phòng', digits=(16, 3), readonly=True)
    so_luong_thieu = fields.Float(string='SL thiếu', digits=(16, 3), readonly=True)
    so_luong_can_mua = fields.Float(string='SL cần mua', digits=(16, 3), readonly=True)
    ghi_chu = fields.Char(string='Ghi chú (B4/B5/B6/B7)', readonly=True)

    # --- B4/B5/B6 (don_gia_ton_kho: B4 tồn đầu; B5/B6 đầu kỳ NVL) ---
    don_gia_ton_kho = fields.Monetary(
        string='Đơn giá tồn kho',
        currency_field='currency_id',
        readonly=True,
    )

    # --- B5/B6 (khớp kh.dat.vat.tu / kh.dat.vat.tu.bcu) ---
    tong_ton_nvl_sl = fields.Float(string='Tồn NVL đầu kỳ', digits=(16, 3), readonly=True)
    gia_tri_ton_nvl_dau_ky = fields.Monetary(
        string='Giá trị tồn NVL đầu kỳ',
        currency_field='currency_id',
        readonly=True,
    )
    tong_sl_vt_can_dung_t0 = fields.Float(string='Cần dùng T0', digits=(16, 3), readonly=True)
    tong_sl_vt_can_dung_t1 = fields.Float(string='Cần dùng T1', digits=(16, 3), readonly=True)
    tong_sl_vt_can_dung_t2 = fields.Float(string='Cần dùng T2', digits=(16, 3), readonly=True)
    tong_sl_vt_can_dung_t3 = fields.Float(string='Cần dùng T3', digits=(16, 3), readonly=True)
    tong_vt_can_dung = fields.Float(string='Tổng cần dùng', digits=(16, 3), readonly=True)
    tong_sl_vt_can_dung = fields.Float(
        string='Tổng SL VT cần dùng (alias)',
        digits=(16, 3),
        readonly=True,
        help='Alias báo cáo; đồng bộ cùng giá trị tong_vt_can_dung.',
    )
    tong_hang_di_duong_sl_t0 = fields.Float(string='Đi đường T0', digits=(16, 3), readonly=True)
    tong_hang_di_duong_sl_t1 = fields.Float(string='Đi đường T1', digits=(16, 3), readonly=True)
    tong_hang_di_duong_sl_t2 = fields.Float(string='Đi đường T2', digits=(16, 3), readonly=True)
    tong_hang_di_duong_sl_t3 = fields.Float(string='Đi đường T3', digits=(16, 3), readonly=True)
    tong_hang_di_duong = fields.Float(string='Tổng đi đường', digits=(16, 3), readonly=True)
    tong_hang_di_duong_sl = fields.Float(
        string='Tổng hàng đi đường (alias)',
        digits=(16, 3),
        readonly=True,
        help='Alias báo cáo; đồng bộ cùng giá trị tong_hang_di_duong.',
    )
    tong_hang_di_duong_dg_t0 = fields.Monetary(
        string='Đi đường ĐG T0', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_dg_t1 = fields.Monetary(
        string='Đi đường ĐG T1', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_dg_t2 = fields.Monetary(
        string='Đi đường ĐG T2', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_dg_t3 = fields.Monetary(
        string='Đi đường ĐG T3', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_gt_t0 = fields.Monetary(
        string='Đi đường GT T0', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_gt_t1 = fields.Monetary(
        string='Đi đường GT T1', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_gt_t2 = fields.Monetary(
        string='Đi đường GT T2', currency_field='currency_id', readonly=True)
    tong_hang_di_duong_gt_t3 = fields.Monetary(
        string='Đi đường GT T3', currency_field='currency_id', readonly=True)
    tong_gia_tri_di_duong = fields.Monetary(
        string='Tổng giá trị đi đường',
        currency_field='currency_id',
        readonly=True,
    )
    # --- B6: hàng đi đường BCU ---
    ve_du_kien_bcu_t0 = fields.Float(string='BCU đi đường T0', digits=(16, 3), readonly=True)
    ve_du_kien_bcu_t1 = fields.Float(string='BCU đi đường T1', digits=(16, 3), readonly=True)
    ve_du_kien_bcu_t2 = fields.Float(string='BCU đi đường T2', digits=(16, 3), readonly=True)
    ve_du_kien_bcu_t3 = fields.Float(string='BCU đi đường T3', digits=(16, 3), readonly=True)
    ve_du_kien_bcu_dg_t0 = fields.Monetary(
        string='BCU đi đường ĐG T0', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_dg_t1 = fields.Monetary(
        string='BCU đi đường ĐG T1', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_dg_t2 = fields.Monetary(
        string='BCU đi đường ĐG T2', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_dg_t3 = fields.Monetary(
        string='BCU đi đường ĐG T3', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_gt_t0 = fields.Monetary(
        string='BCU đi đường GT T0', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_gt_t1 = fields.Monetary(
        string='BCU đi đường GT T1', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_gt_t2 = fields.Monetary(
        string='BCU đi đường GT T2', currency_field='currency_id', readonly=True)
    ve_du_kien_bcu_gt_t3 = fields.Monetary(
        string='BCU đi đường GT T3', currency_field='currency_id', readonly=True)
    tong_ve_du_kien_bcu = fields.Float(string='Tổng SL đi đường BCU', digits=(16, 3), readonly=True)
    tong_gia_tri_bcu = fields.Monetary(
        string='Tổng GT đi đường BCU', currency_field='currency_id', readonly=True)
    # --- B7: phê duyệt ---
    khoi_luong_don_vi_dat = fields.Float(
        string='Khối lượng đơn vị đặt', digits=(16, 3), readonly=True)
    khoi_luong_bcu_dat = fields.Float(
        string='Khối lượng BCU đặt', digits=(16, 3), readonly=True)
    leadtime_ngay = fields.Integer(string='Leadtime (ngày)', readonly=True)
    ngay_co_so = fields.Date(string='Ngày cơ sở kế hoạch', readonly=True)
    ngay_du_kien_ve = fields.Date(string='Dự kiến về kho', readonly=True)
    thoi_diem_giao_dvtv = fields.Char(
        string='Giao về đơn vị thành viên theo leadtime', readonly=True)
    thoi_diem_su_dung = fields.Char(string='Thời điểm sử dụng', readonly=True)
    sl_du_tru_toi_thieu = fields.Float(string='SL dự trữ tối thiểu', digits=(16, 3), readonly=True)
    sl_dat_mua_de_xuat = fields.Float(string='SL đặt mua đề xuất', digits=(16, 3), readonly=True)
    sl_dat_mua_chot = fields.Float(string='SL đặt mua chốt', digits=(16, 3), readonly=True)
    sl_can_mua_theo_moq = fields.Float(string='SL cần mua dựa theo MOQ NCC', digits=(16, 3), readonly=True)
    don_gia_mua = fields.Monetary(
        string='Đơn giá mua',
        currency_field='currency_id',
        readonly=True,
    )
    gia_tri_mua_hang = fields.Monetary(
        string='Giá trị mua hàng',
        currency_field='currency_id',
        readonly=True,
    )
    sl_ton_kho_cuoi_ky = fields.Float(string='Tồn kho cuối kỳ', digits=(16, 3), readonly=True)
    sl_ton_kho = fields.Float(
        string='SL tồn kho (alias)',
        digits=(16, 3),
        readonly=True,
        help='Alias báo cáo; đồng bộ cùng giá trị sl_ton_kho_cuoi_ky.',
    )
    vt_loi_ton_lau = fields.Float(string='VT lỗi, tồn lâu ngày', digits=(16, 3), readonly=True)
    so_ngay_vong_quay_ton = fields.Float(string='Ngày vòng quay tồn', digits=(16, 2), readonly=True)
    don_gia_ton_kho_cuoi_ky = fields.Monetary(
        string='Đơn giá tồn cuối kỳ',
        currency_field='currency_id',
        readonly=True,
    )
    gia_tri_ton_kho_cuoi_ky = fields.Monetary(
        string='Giá trị tồn kho cuối kỳ',
        currency_field='currency_id',
        readonly=True,
    )
    gia_tri_ton_kho = fields.Monetary(
        string='Giá trị tồn kho (alias)',
        currency_field='currency_id',
        readonly=True,
        help='Alias báo cáo; đồng bộ cùng giá trị gia_tri_ton_kho_cuoi_ky.',
    )

    display_name = fields.Char(compute='_compute_display_name')

    _sql_constraints = [
        ('uniq_dlthvt_source',
         'unique(source_model, source_res_id, month_key)',
         'Mỗi dòng nguồn và tháng chỉ có một bản ghi tổng hợp.'),
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
        # Một file duy nhất: trigger + mapping + sync BOM từ SAP.
        # fn_bom_chuoi_cung_ung / bom_tinh_toan do a QL quản trên DB, không
        # nằm trong module — tránh CREATE OR REPLACE ghi đè khi upgrade.
        self._cr.execute(_read_dlthvt_sync_sql())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SQL_DIR = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'sql',
)

_SQL_DLTHVT_SYNC_PATH = _os.path.join(_SQL_DIR, 'dlthvt_sync.sql')

def _read_dlthvt_sync_sql():
    """Đọc file data/sql/dlthvt_sync.sql (toàn bộ tầng đồng bộ bảng phẳng)."""
    with open(_SQL_DLTHVT_SYNC_PATH, 'r', encoding='utf-8') as f:
        return f.read()

