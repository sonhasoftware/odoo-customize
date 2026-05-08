# -*- coding: utf-8 -*-
import re
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class KeHoachVatTu(models.Model):
    _name = 'ke.hoach.vat.tu'
    _description = 'Kỳ kế hoạch vật tư cần'
    _order = 'period_month desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tên kỳ', tracking=True)
    period_month = fields.Char(
        string='Tháng bắt đầu', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Công ty', tracking=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('ke_hoach', 'Kế hoạch thành phẩm'),
        ('dinh_muc', 'Định mức kỳ'),
        ('tinh_toan', 'Tính toán vật tư'),
        ('tong_hop', 'Tổng hợp vật tư cần sản xuất'),
        ('dat_hang', 'Kế hoạch đặt vật tư'),
    ], default='ke_hoach', tracking=True, string='Trạng thái')
    note = fields.Text(string='Ghi chú')

    # Tham số ước lượng số ngày trong công thức chia cho (28 × ngày). Hai bước độc lập:
    # B4: dự phòng; B5: dự trữ (Excel thường dùng 15 vs 20). Có thể chỉnh theo từng kỳ.
    ngay_du_phong_b4 = fields.Float(
        string='Số ngày (B4 - dự phòng)',
        default=15.0,
        digits=(16, 2),
        help='Dùng cho B4: số lượng dự phòng = VT cần dùng ÷ (28 × số ngày này).',
        tracking=True,
    )
    ngay_du_tru_b5 = fields.Float(
        string='Số ngày (B5 - dự trữ)',
        default=20.0,
        digits=(16, 2),
        help='Dùng cho B5: số lượng dự trữ tối thiểu = VT cần dùng ÷ (28 × số ngày này).',
        tracking=True,
    )

    ke_hoach_thanh_pham_ids = fields.One2many('ke.hoach.thanh.pham', 'period_id', string='B1 - KH thành phẩm')
    dinh_muc_ids = fields.One2many('dinh.muc', 'period_id', string='B2 - Định mức tháng')
    tinh_toan_vat_tu_ids = fields.One2many('tinh.toan.vat.tu', 'period_id', string='B3 - Tính toán vật tư')
    tong_hop_vat_tu_ids = fields.One2many('tong.hop.vat.tu', 'period_id', string='B4 - Tổng hợp vật tư')
    kh_dat_vat_tu_ids = fields.One2many('kh.dat.vat.tu', 'period_id', string='B5 - Kế hoạch đặt vật tư')

    ke_hoach_thanh_pham_count = fields.Integer(compute='_compute_counts')
    dinh_muc_count = fields.Integer(compute='_compute_counts')
    tinh_toan_vat_tu_count = fields.Integer(compute='_compute_counts')
    tong_hop_vat_tu_count = fields.Integer(compute='_compute_counts')
    kh_dat_vat_tu_count = fields.Integer(compute='_compute_counts')
    month_ids_preview = fields.Char(
        string='Các tháng có dữ liệu',
        compute='_compute_month_preview')



    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Tên kỳ phải duy nhất!'),
    ]

    @api.constrains('period_month')
    def _check_period_month(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.period_month and not pattern.match(rec.period_month):
                raise ValidationError('Tháng bắt đầu phải đúng định dạng MM/YYYY, ví dụ 04/2026.')

    @api.constrains('ngay_du_phong_b4', 'ngay_du_tru_b5')
    def _check_tham_so_ngay(self):
        for rec in self:
            if rec.ngay_du_phong_b4 is not False and rec.ngay_du_phong_b4 <= 0:
                raise ValidationError(
                    _('Số ngày B4 phải lớn hơn 0 (đang là %s).') % rec.ngay_du_phong_b4)
            if rec.ngay_du_tru_b5 is not False and rec.ngay_du_tru_b5 <= 0:
                raise ValidationError(
                    _('Số ngày B5 phải lớn hơn 0 (đang là %s).') % rec.ngay_du_tru_b5)

    @api.depends('ke_hoach_thanh_pham_ids', 'dinh_muc_ids', 'tinh_toan_vat_tu_ids',
                 'tong_hop_vat_tu_ids', 'kh_dat_vat_tu_ids')
    def _compute_counts(self):
        for rec in self:
            rec.ke_hoach_thanh_pham_count = len(rec.ke_hoach_thanh_pham_ids)
            rec.dinh_muc_count = len(rec.dinh_muc_ids)
            rec.tinh_toan_vat_tu_count = len(rec.tinh_toan_vat_tu_ids)
            rec.tong_hop_vat_tu_count = len(rec.tong_hop_vat_tu_ids)
            rec.kh_dat_vat_tu_count = len(rec.kh_dat_vat_tu_ids)

    @api.depends('ke_hoach_thanh_pham_ids.month_key')
    def _compute_month_preview(self):
        for rec in self:
            def _sort_key(mm_yyyy):
                try:
                    month, year = mm_yyyy.split('/')
                    return int(year), int(month)
                except Exception:
                    return 0, 0
            months = sorted(
                {p.month_key for p in rec.ke_hoach_thanh_pham_ids if p.month_key},
                key=_sort_key
            )
            rec.month_ids_preview = ', '.join(months) or False


    def _call_db_function(self, fn_name):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT routine_name FROM information_schema.routines "
            "WHERE routine_name = %s AND routine_schema = 'public' LIMIT 1",
            (fn_name,))
        if not self.env.cr.fetchone():
            raise UserError(_(
                'Chưa có function DB "%s" để tính. Function này do team DB '
                'cung cấp; nhánh Odoo đang chờ ghép nối.'
            ) % fn_name)
        self.env.cr.execute('SELECT %s(%%s)' % fn_name, (self.id,))

    def _run_db_or_demo(self, fn_name, demo_method_name):
        self.ensure_one()
        self.env.cr.execute(
            "SELECT routine_name FROM information_schema.routines "
            "WHERE routine_name = %s AND routine_schema = 'public' LIMIT 1",
            (fn_name,))
        if self.env.cr.fetchone():
            self.env.cr.execute('SELECT %s(%%s)' % fn_name, (self.id,))
            return
        getattr(self, demo_method_name)()

    def _generate_b2_demo(self):
        self.ensure_one()
        Bom = self.env['bom'].sudo()
        DinhMuc = self.env['dinh.muc'].sudo()
        self.dinh_muc_ids.unlink()
        vals_list = []
        for line in self.ke_hoach_thanh_pham_ids:
            if not line.ma_sap:
                continue
            bom_lines = Bom.search([
                ('company_id', '=', line.company_id.id),
                ('ma_tp', '=', line.ma_sap),
            ])
            for bom_line in bom_lines:
                vals_list.append({
                    'period_id': self.id,
                    'company_id': line.company_id.id,
                    'ma_sap': line.ma_sap,
                    'ten_sap': bom_line.ten_tp,
                    'ma_tp': bom_line.ma_tp,
                    'ma_nvl': bom_line.ma_nvl,
                    'month_key': line.month_key,
                    'qty': (line.qty or 0.0) * (bom_line.sl_dinh_muc or 0.0),
                })
        if vals_list:
            DinhMuc.create(vals_list)

    def _compute_b3_demo(self):
        self.ensure_one()
        Bom = self.env['bom'].sudo()
        B3 = self.env['tinh.toan.vat.tu'].sudo()
        self.tinh_toan_vat_tu_ids.unlink()
        vals_list = []
        density = 7.63  # theo file Excel: nhân 7.63 rồi chia 1,000,000
        for b2 in self.dinh_muc_ids:
            bom_line = Bom.search([
                ('company_id', '=', b2.company_id.id),
                ('ma_tp', '=', b2.ma_tp),
                ('ma_nvl', '=', b2.ma_nvl),
            ], limit=1)
            kho_1 = bom_line.kho_1 if bom_line else 0.0
            kho_2 = bom_line.kho_2 if bom_line else 0.0
            do_day = bom_line.do_day if bom_line else 0.0
            trong_luong_kg_tam = (do_day * kho_1 * kho_2 * density) / 1000000.0
            qty_kg = (b2.qty or 0.0) * (trong_luong_kg_tam or 1.0)
            vals_list.append({
                'period_id': self.id,
                'company_id': b2.company_id.id,
                'ma_sap': b2.ma_sap,
                'ma_effect': b2.ma_nvl or (bom_line.ma_nvl if bom_line else False),
                'ten_sap': b2.ten_sap,
                'don_vi_tinh': 'kg',
                'do_day': do_day,
                'kho_1': kho_1,
                'kho_2': kho_2,
                'trong_luong_kg_tam': trong_luong_kg_tam,
                'sl_dinh_muc': False,
                'month_key': b2.month_key,
                'qty': qty_kg,
            })
        if vals_list:
            B3.create(vals_list)

    def _compute_b4_demo(self):
        self.ensure_one()
        B4 = self.env['tong.hop.vat.tu'].sudo()
        VatDuong = self.env['vat.tu.di.duong'].sudo()
        self.tong_hop_vat_tu_ids.unlink()

        # Gom nhu cầu từ B3 theo (company, material_code, month_key)
        grouped = defaultdict(float)
        for b3 in self.tinh_toan_vat_tu_ids:
            key = (
                b3.company_id.id,
                b3.ma_sap or '',
                b3.ma_effect or b3.ma_sap or '',
            )
            # Dùng tuple (month_key, key) để giữ thứ tự tháng
            grouped[(key, b3.month_key)] += b3.qty or 0.0

        # Sắp xếp theo material_code rồi theo month_key để cuốn chiếu đúng
        sorted_keys = sorted(grouped.keys(), key=lambda x: (x[0], x[1]))

        days_in_formula = 28.0
        ngay_dp = self.ngay_du_phong_b4 or 15.0
        divisor_b4 = days_in_formula * ngay_dp

        # Cache tồn cuối để cuốn chiếu: key = (company_id, material_code)
        ton_cuoi_cache = {}

        # Cache đơn giá tồn kho từ SAP: key = material_code
        don_gia_cache = {}

        vals_list = []
        for (material_key, month_key), demand_qty in sorted_keys:
            company_id, ma_sap, material_code = material_key[0], material_key[1], material_key[2]
            demand_qty = grouped[(material_key, month_key)]
            cache_key = (company_id, material_code)

            # --- Tồn đầu: cuốn chiếu ---
            if cache_key in ton_cuoi_cache:
                # Tháng tiếp: tồn đầu = tồn cuối tháng trước
                ton_dau = ton_cuoi_cache[cache_key]
            else:
                # Tháng đầu: lấy từ SAP
                ton_dau = 0.0
                if material_code:
                    self.env.cr.execute("""
                        SELECT safe_sap_numeric(ton_dau)
                        FROM md_sap_ton_kho
                        WHERE TRIM(ma_hang) = %s
                        ORDER BY create_date DESC LIMIT 1
                    """, (material_code,))
                    row = self.env.cr.fetchone()
                    if row and row[0]:
                        ton_dau = float(row[0])

            # --- Đơn giá tồn kho từ SAP (cache lần đầu) ---
            if material_code not in don_gia_cache:
                don_gia = 0.0
                if material_code:
                    self.env.cr.execute("""
                        SELECT safe_sap_numeric(tien_ton_dau),
                               safe_sap_numeric(ton_dau)
                        FROM md_sap_ton_kho
                        WHERE TRIM(ma_hang) = %s
                        ORDER BY create_date DESC LIMIT 1
                    """, (material_code,))
                    row = self.env.cr.fetchone()
                    if row and row[1] and float(row[1]) != 0:
                        don_gia = float(row[0]) / float(row[1])
                don_gia_cache[material_code] = don_gia

            # --- Vật tư đi đường ---
            ve_du_kien = 0.0
            if material_code:
                vdd = VatDuong.search(
                    [
                        ('company_id', '=', company_id),
                        ('month_key', '=', month_key),
                        ('ma_sap', '=', material_code),
                    ],
                    limit=1,
                )
                ve_du_kien = vdd.so_luong if vdd else 0.0

            so_luong_du_phong = (
                (demand_qty / divisor_b4) if demand_qty else 0.0)
            ton_cuoi = ton_dau + ve_du_kien - demand_qty
            so_luong_thieu = max(0.0, so_luong_du_phong - ton_cuoi)

            # Lưu tồn cuối để cuốn chiếu sang tháng sau
            ton_cuoi_cache[cache_key] = ton_cuoi

            vals_list.append({
                'period_id': self.id,
                'company_id': company_id,
                'ma_dat_hang': material_code,
                'ma_sap': ma_sap,
                'chung_loai': material_code,
                'don_vi_tinh': 'kg',
                'month_key': month_key,
                'ton_dau': ton_dau,
                've_du_kien': ve_du_kien,
                'vt_can_dung': demand_qty,
                'ton_cuoi': ton_cuoi,
                'so_luong_du_phong': so_luong_du_phong,
                'so_luong_thieu': so_luong_thieu,
                'so_luong_can_mua': so_luong_thieu,
            })
        if vals_list:
            B4.create(vals_list)

    def _compute_b5_demo(self):
        self.ensure_one()
        B5 = self.env['kh.dat.vat.tu'].sudo()
        self.kh_dat_vat_tu_ids.unlink()
        days_in_formula = 28.0
        ngay_dt = self.ngay_du_tru_b5 or 20.0
        divisor_b5 = days_in_formula * ngay_dt

        # Cache đơn giá tồn kho từ SAP
        don_gia_cache = {}

        vals_list = []
        for b4 in self.tong_hop_vat_tu_ids:
            vt_can_dung = b4.vt_can_dung or 0.0
            sl_du_tru_toi_thieu = (
                (vt_can_dung / divisor_b5) if vt_can_dung else 0.0)
            so_luong_can_mua = b4.so_luong_can_mua or 0.0
            material_code = b4.ma_dat_hang or b4.ma_sap

            # Lấy đơn giá tồn kho từ SAP (cache)
            if material_code not in don_gia_cache:
                don_gia = 0.0
                if material_code:
                    self.env.cr.execute("""
                        SELECT safe_sap_numeric(tien_ton_dau),
                               safe_sap_numeric(ton_dau)
                        FROM md_sap_ton_kho
                        WHERE TRIM(ma_hang) = %s
                        ORDER BY create_date DESC LIMIT 1
                    """, (material_code,))
                    row = self.env.cr.fetchone()
                    if row and row[1] and float(row[1]) != 0:
                        don_gia = float(row[0]) / float(row[1])
                don_gia_cache[material_code] = don_gia

            vals_list.append({
                'period_id': self.id,
                'company_id': b4.company_id.id,
                'month_key': b4.month_key,
                'ma_sap': b4.ma_sap,
                'ma_effect': b4.ma_dat_hang or b4.ma_sap,
                'chung_loai': b4.chung_loai,
                'don_vi_tinh': b4.don_vi_tinh or 'kg',
                'tong_ton_nvl_sl': b4.ton_dau,
                'tong_hang_di_duong_sl': b4.ve_du_kien,
                'tong_sl_vt_can_dung': b4.vt_can_dung,
                'sl_du_tru_toi_thieu': sl_du_tru_toi_thieu,
                'sl_can_mua_theo_moq': False,
                'don_gia_ton_kho': don_gia_cache.get(material_code, 0.0),
            })
        if vals_list:
            B5.create(vals_list)

    def action_generate_b2(self):
        self.ensure_one()
        self._generate_b2_demo()
        self.state = 'dinh_muc'
        return self.action_open_step_b2()

    def action_compute_b3(self):
        self.ensure_one()
        self._run_db_or_demo('fn_vtc_compute_b3', '_compute_b3_demo')
        self.state = 'tinh_toan'
        return self.action_open_step_b3()

    def action_compute_b4(self):
        self.ensure_one()
        self._run_db_or_demo('fn_vtc_compute_b4', '_compute_b4_demo')
        self.state = 'tong_hop'
        return self.action_open_step_b4()

    def action_compute_b5(self):
        self.ensure_one()
        self._run_db_or_demo('fn_vtc_compute_b5', '_compute_b5_demo')
        self.state = 'dat_hang'
        return self.action_open_step_b5()

    def action_reset_to_draft(self):
        for period in self:
            period.message_post(body=_('%s đã reset về nháp.') % self.env.user.name)
            period.dinh_muc_ids.unlink()
            period.tinh_toan_vat_tu_ids.unlink()
            period.tong_hop_vat_tu_ids.unlink()
            period.kh_dat_vat_tu_ids.unlink()
            period.state = 'ke_hoach'

    def action_download_b1_template(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/sonha_vat_tu/static/xls/ke_hoach_vat_tu_templates.xlsx',
            'target': 'self',
        }

    def action_open_import_wizard(self):
        self.ensure_one()
        return {
            'name': _('Import kế hoạch thành phẩm'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
            },
        }

    def _action_open_step(self, view_xmlid):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Kế hoạch vật tư'),
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(view_xmlid).id, 'form')],
            'target': 'current',
        }

    def action_open_step_b1(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b1')

    def action_open_step_b2(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b2')

    def action_open_step_b3(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b3')

    def action_open_step_b4(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b4')

    def action_open_step_b5(self):
        return self._action_open_step('sonha_vat_tu.view_ke_hoach_vat_tu_form_b5')
