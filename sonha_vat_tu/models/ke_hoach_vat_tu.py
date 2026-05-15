# -*- coding: utf-8 -*-
from datetime import date
import os as _os
import re
import base64
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_SQL_FUNCTIONS_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'fn_ke_hoach_vat_tu.sql',
)


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
        ('ke_hoach', 'Kế hoạch sản xuất'),
        ('dinh_muc', 'Định mức kỳ'),
        ('tinh_toan', 'Tính toán vật tư'),
        ('tong_hop', 'Tổng hợp vật tư cần sản xuất'),
        ('dat_hang', 'Kế hoạch đặt vật tư'),
    ], default='ke_hoach', tracking=True, string='Trạng thái')
    note = fields.Text(string='Ghi chú')

    ngay_du_phong_b4 = fields.Float(
        string='Số ngày (dự phòng)',
        default=15.0,
        digits=(16, 2),
        help='Dùng cho B4: số lượng dự phòng = VT cần dùng ÷ (28 × số ngày này).',
        tracking=True,
    )
    ngay_du_tru_b5 = fields.Float(
        string='Số ngày (dự trữ)',
        default=20.0,
        digits=(16, 2),
        help='Dùng cho B5: số lượng dự trữ tối thiểu = VT cần dùng ÷ (28 × số ngày này).',
        tracking=True,
    )

    ke_hoach_kinh_doanh_ids = fields.One2many('ke.hoach.kinh.doanh', 'period_id', string='Kế hoạch kinh doanh')
    ke_hoach_san_xuat_ids = fields.One2many('ke.hoach.san.xuat', 'period_id', string='Kế hoạch sản xuất')
    dinh_muc_ids = fields.One2many('dinh.muc', 'period_id', string='Định mức tháng')
    tinh_toan_vat_tu_ids = fields.One2many('tinh.toan.vat.tu', 'period_id', string='Tính toán vật tư')
    tong_hop_vat_tu_ids = fields.One2many('tong.hop.vat.tu', 'period_id', string='Tổng hợp vật tư')
    kh_dat_vat_tu_ids = fields.One2many('kh.dat.vat.tu', 'period_id', string='Kế hoạch đặt vật tư')

    ke_hoach_kinh_doanh_count = fields.Integer(compute='_compute_counts')
    ke_hoach_san_xuat_count = fields.Integer(compute='_compute_counts')
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

    @api.model
    def init(self):
        with open(_SQL_FUNCTIONS_PATH, 'r', encoding='utf-8') as f:
            self.env.cr.execute(f.read())

    @api.model
    def _month_key_to_date(self, month_key):
        if not month_key:
            return False
        try:
            month, year = str(month_key).split('/')
            return date(int(year), int(month), 1)
        except Exception:
            return False

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

    @api.depends('ke_hoach_kinh_doanh_ids', 'ke_hoach_san_xuat_ids', 'dinh_muc_ids', 'tinh_toan_vat_tu_ids',
                 'tong_hop_vat_tu_ids', 'kh_dat_vat_tu_ids')
    def _compute_counts(self):
        for rec in self:
            rec.ke_hoach_kinh_doanh_count = len(rec.ke_hoach_kinh_doanh_ids)
            rec.ke_hoach_san_xuat_count = len(rec.ke_hoach_san_xuat_ids)
            rec.dinh_muc_count = len(rec.dinh_muc_ids)
            rec.tinh_toan_vat_tu_count = len(rec.tinh_toan_vat_tu_ids)
            rec.tong_hop_vat_tu_count = len(rec.tong_hop_vat_tu_ids)
            rec.kh_dat_vat_tu_count = len(rec.kh_dat_vat_tu_ids)

    @api.depends('ke_hoach_san_xuat_ids.month_key')
    def _compute_month_preview(self):
        for rec in self:
            def _sort_key(mm_yyyy):
                try:
                    month, year = mm_yyyy.split('/')
                    return int(year), int(month)
                except Exception:
                    return 0, 0
            months = sorted(
                {p.month_key for p in rec.ke_hoach_san_xuat_ids if p.month_key},
                key=_sort_key
            )
            rec.month_ids_preview = ', '.join(months) or False

    # ------------------------------------------------------------------
    # Actions — gọi thẳng SQL Procedure
    # ------------------------------------------------------------------

    def action_generate_b2(self):
        self.ensure_one()
        self.env.cr.execute('CALL public.fn_sinh_dinh_muc(%s)', (self.id,))
        self.state = 'dinh_muc'
        return self.action_open_step_b2()

    def action_compute_b3(self):
        self.ensure_one()
        self.env.cr.execute('CALL public.fn_tinh_toan_vat_tu(%s)', (self.id,))
        self.state = 'tinh_toan'
        return self.action_open_step_b3()

    def action_compute_b4(self):
        self.ensure_one()
        self.env.cr.execute(
            'CALL public.fn_tong_hop_vat_tu(%s, %s)',
            (self.id, self.ngay_du_phong_b4 or 15.0)
        )
        self.state = 'tong_hop'
        return self.action_open_step_b4()

    def action_compute_b5(self):
        self.ensure_one()
        self.env.cr.execute(
            'CALL public.fn_ke_hoach_dat_vat_tu(%s, %s)',
            (self.id, self.ngay_du_tru_b5 or 20.0)
        )
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
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch đã sang bước sau, không thể tải template để import lại.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền tải template kế hoạch kinh doanh.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/sonha_vat_tu/static/xls/ke_hoach_vat_tu_templates.xlsx',
            'target': 'self',
        }

    def action_open_import_kinh_doanh_wizard(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch kinh doanh đã khóa vì kỳ kế hoạch đã sang bước sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền import kế hoạch kinh doanh.'))
        return {
            'name': _('Import kế hoạch kinh doanh'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_import_type': 'business',
            },
        }

    def action_open_import_san_xuat_wizard(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch sản xuất đã khóa vì kỳ kế hoạch đã sang bước sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền import kế hoạch sản xuất.'))
        return {
            'name': _('Import kế hoạch sản xuất'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_period_id': self.id,
                'default_import_type': 'production',
            },
        }

    def action_open_import_wizard(self):
        return self.action_open_import_kinh_doanh_wizard()

    def action_export_san_xuat(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Kế hoạch đã sang bước sau, không thể export lại cho sản xuất.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Bạn không có quyền export kế hoạch cho sản xuất.'))
        lines = self.ke_hoach_kinh_doanh_ids.sorted(lambda r: (
            r.nganh_hang_id.name or '',
            r.dong_hang_id.name or '',
            r.ma_hang_id.code or '',
            r.ma_sap or '',
            r.month_date or date.min,
        ))
        if not lines:
            raise UserError(_('Chưa có kế hoạch kinh doanh để export cho sản xuất.'))

        months = sorted(
            {line.month_key for line in lines if line.month_key},
            key=lambda month: self._month_key_to_date(month) or date.min,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach san xuat'
        headers = ['Ngành hàng', 'Dòng hàng', 'Mã hàng', 'Mã SAP']
        headers += ['Tháng %s' % month for month in months]
        headers += ['Đơn vị sản xuất']
        ws.append(headers)

        grouped = {}
        for line in lines:
            key = (
                line.nganh_hang_id.name or '',
                line.dong_hang_id.name or '',
                line.ma_hang_id.code or '',
                line.ma_sap or '',
            )
            grouped.setdefault(key, {})
            grouped[key][line.month_key] = grouped[key].get(line.month_key, 0.0) + (line.qty or 0.0)

        for key, qty_by_month in grouped.items():
            ws.append(list(key) + [qty_by_month.get(month, 0.0) for month in months] + [''])

        base_font = Font(name='Times New Roman', size=10)
        header_font = Font(name='Times New Roman', size=10, bold=True)
        header_fill = PatternFill(fill_type='solid', fgColor='FFF2CC')
        thin_side = Side(style='thin', color='000000')
        header_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_alignment = Alignment(horizontal='center', vertical='center')
        body_alignment = Alignment(vertical='center')

        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=len(headers)):
            for cell in row:
                cell.font = base_font
                cell.alignment = body_alignment
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = header_border
            cell.alignment = header_alignment
        ws.freeze_panes = 'A2'

        companies = self.env['res.company'].sudo().search([
            ('company_code', 'in', ['BNH', 'SSP']),
        ], order='name')
        company_names = companies.mapped('name') or ['BNH', 'SSP']
        list_ws = wb.create_sheet('_lists')
        for row_idx, company_name in enumerate(company_names, start=1):
            list_ws.cell(row=row_idx, column=1, value=company_name)
        list_ws.sheet_state = 'hidden'
        validation = DataValidation(
            type='list',
            formula1="'_lists'!$A$1:$A$%s" % len(company_names),
            allow_blank=False,
        )
        ws.add_data_validation(validation)
        company_col = len(headers)
        for row in range(2, ws.max_row + 1):
            validation.add(ws.cell(row=row, column=company_col))

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 28)
        ws.column_dimensions['A'].width = 22
        ws.column_dimensions['B'].width = 22
        ws.column_dimensions['C'].width = 24
        ws.column_dimensions['D'].width = 24
        ws.column_dimensions[ws.cell(row=1, column=company_col).column_letter].width = 42

        output = io.BytesIO()
        wb.save(output)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': 'ke_hoach_san_xuat_%s.xlsx' % (self.period_month or self.id),
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
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
