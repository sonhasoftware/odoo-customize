# -*- coding: utf-8 -*-
import calendar
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class PheDuyetKhVatTu(models.Model):
    _name = 'phe.duyet.kh.vat.tu'
    _description = 'Phê duyệt kế hoạch vật tư'
    _order = 'period_id, company_id, ma_sap, id'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ', ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng', index=True,
        help='Đơn vị sản xuất đặt hàng (BNH, SSP…).')
    ma_sap = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    don_vi_tinh = fields.Many2one('mdm.dvt', string='ĐVT')

    khoi_luong_don_vi_dat = fields.Float(
        string='Khối lượng đơn vị đặt',
        digits=(16, 3),
        help='Sản lượng đặt mua chốt đơn vị thành viên — lấy từ B5.',
    )
    khoi_luong_bcu_dat = fields.Float(
        string='Khối lượng BCU đặt',
        digits=(16, 3),
        help='SL cần mua dựa theo BCU — lấy từ B6.',
    )

    leadtime_ngay = fields.Integer(
        string='Leadtime (ngày)',
        help='Đồng bộ 2 chiều với Danh mục → Cấu hình leadtime.',
    )
    ngay_co_so = fields.Date(
        string='Ngày cơ sở kế hoạch',
        help='Ngày chọn tháng kế hoạch (I1/R1 trong Excel).',
    )
    ngay_du_kien_ve = fields.Date(
        string='Dự kiến về kho',
        compute='_compute_thoi_diem',
        store=True,
        help='BB = ngày cơ sở + leadtime.',
    )
    thoi_diem_giao_dvtv = fields.Char(
        string='Giao về đơn vị thành viên theo leadtime',
        compute='_compute_thoi_diem',
        store=True,
        help='Cột BZ trong Excel.',
    )
    thoi_diem_su_dung = fields.Char(
        string='Thời điểm sử dụng',
        compute='_compute_thoi_diem',
        store=True,
        help='Cột CA trong Excel.',
    )
    ghi_chu = fields.Text(string='Ghi chú')

    @staticmethod
    def _month_text(anchor, month_offset):
        if not anchor:
            return ''
        dt = anchor + relativedelta(months=month_offset)
        return '%02d-%d' % (dt.month, dt.year)

    @staticmethod
    def _last_day_of_month(anchor, month_offset):
        if not anchor:
            return 0
        dt = anchor + relativedelta(months=month_offset)
        return calendar.monthrange(dt.year, dt.month)[1]

    @classmethod
    def _compute_bz(cls, anchor, leadtime, bcu_qty):
        """Thời điểm giao về đơn vị thành viên theo leadtime — cột BZ Excel."""
        if not anchor or not leadtime or not (bcu_qty or 0):
            return ''
        lt = int(leadtime)
        if lt <= 29:
            mm = cls._month_text(anchor, 1)
            return '01 ->05th %s' % mm
        if 30 <= lt <= 45:
            mm = cls._month_text(anchor, 1)
            last = cls._last_day_of_month(anchor, 1)
            return '25 ->%02dth %s' % (last, mm)
        if 46 <= lt <= 50:
            mm = cls._month_text(anchor, 2)
            return '01 ->05th %s' % mm
        if 51 <= lt <= 55:
            mm = cls._month_text(anchor, 2)
            return '10 ->15th %s' % mm
        if 56 <= lt <= 60:
            mm = cls._month_text(anchor, 2)
            return '15 ->20th %s' % mm
        if 61 <= lt <= 65:
            mm = cls._month_text(anchor, 2)
            return '20 ->25th %s' % mm
        if 66 <= lt <= 75:
            mm = cls._month_text(anchor, 2)
            last = cls._last_day_of_month(anchor, 1)
            return '25 ->%02dth %s' % (last, mm)
        if 90 <= lt < 120:
            mm = cls._month_text(anchor, 3)
            return '15->20th %s' % mm
        if 120 <= lt < 150:
            mm = cls._month_text(anchor, 4)
            return '10->20th %s' % mm
        if lt >= 150:
            mm = cls._month_text(anchor, 5)
            return '10->20th %s' % mm
        return ''

    @classmethod
    def _compute_ca(cls, anchor, leadtime, bcu_qty):
        """Thời điểm sử dụng vật tư — cột CA Excel."""
        if not anchor or not leadtime or not (bcu_qty or 0):
            return ''
        lt = int(leadtime)
        if lt <= 29:
            offset = 1
        elif lt <= 45:
            offset = 2
        elif lt <= 65:
            offset = 2
        elif lt <= 90:
            offset = 3
        elif lt < 120:
            offset = 4
        else:
            offset = 5
        return cls._month_text(anchor, offset)

    @api.depends(
        'ngay_co_so',
        'leadtime_ngay',
        'khoi_luong_bcu_dat',
    )
    def _compute_thoi_diem(self):
        for rec in self:
            anchor = rec.ngay_co_so
            lt = rec.leadtime_ngay or 0
            bcu = rec.khoi_luong_bcu_dat or 0
            if anchor and lt and bcu:
                rec.ngay_du_kien_ve = anchor + relativedelta(days=lt)
            else:
                rec.ngay_du_kien_ve = False
            rec.thoi_diem_giao_dvtv = self._compute_bz(anchor, lt, bcu)
            rec.thoi_diem_su_dung = self._compute_ca(anchor, lt, bcu)

    @api.model
    def default_ngay_co_so_from_period(self, period):
        if not period or not period.period_month:
            return False
        return period.month_start_from_key(period.period_month)

    def write(self, vals):
        res = super().write(vals)
        if 'leadtime_ngay' in vals and not self.env.context.get('skip_leadtime_sync'):
            self._sync_to_cau_hinh_leadtime()
        return res

    def _sync_to_cau_hinh_leadtime(self):
        Config = self.env['cau.hinh.leadtime'].sudo()
        for rec in self:
            Config._upsert_from_phe_duyet(rec)

    def _apply_leadtime_from_config(self):
        """Nạp leadtime từ master khi sinh B7 (B6 → B7)."""
        codes = list({
            (rec.ma_sap or '').strip()
            for rec in self
            if (rec.ma_sap or '').strip()
        })
        if not codes:
            return
        configs = {
            (cfg.ma_nvl or '').strip(): cfg
            for cfg in self.env['cau.hinh.leadtime'].sudo().search([
                ('ma_nvl', 'in', codes),
                ('leadtime_ngay', '>', 0),
            ])
        }
        sync_ctx = {'skip_leadtime_sync': True}
        for rec in self:
            ma = (rec.ma_sap or '').strip()
            cfg = configs.get(ma)
            if not cfg:
                continue
            rec.with_context(**sync_ctx).write({
                'leadtime_ngay': cfg.leadtime_ngay,
            })
