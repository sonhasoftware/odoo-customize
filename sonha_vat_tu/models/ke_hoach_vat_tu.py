# -*- coding: utf-8 -*-
from datetime import date
import os as _os
import re
import base64
import io

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.styles import Protection
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .mail_message import VAT_TU_CHATTER_SCOPES


_SQL_FUNCTIONS_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'fn_ke_hoach_vat_tu.sql',
)


class KeHoachVatTu(models.Model):
    _name = 'ke.hoach.vat.tu'
    _description = 'Ká»³ káº¿ hoáº¡ch váº­t tÆ° cáº§n'
    _rec_name = 'code'
    _order = 'period_month desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(string='MÃ£', readonly=True, copy=False, index=True, tracking=True)
    period_month = fields.Char(
        string='ThÃ¡ng báº¯t Ä‘áº§u', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='CÃ´ng ty', tracking=True,
        default=lambda self: self.env.company)
    state = fields.Selection([
        ('ke_hoach', 'Káº¿ hoáº¡ch sáº£n xuáº¥t'),
        ('dinh_muc', 'Äá»‹nh má»©c ká»³'),
        ('tinh_toan', 'TÃ­nh toÃ¡n váº­t tÆ°'),
        ('tong_hop', 'Tá»•ng há»£p váº­t tÆ° cáº§n sáº£n xuáº¥t'),
        ('dat_hang', 'Káº¿ hoáº¡ch Ä‘áº·t váº­t tÆ°'),
    ], default='ke_hoach', tracking=True, string='Tráº¡ng thÃ¡i')
    note = fields.Text(string='Ghi chÃº')

    ngay_du_phong_b4 = fields.Float(
        string='Sá»‘ ngÃ y (dá»± phÃ²ng)',
        default=15.0,
        digits=(16, 2),
        help='DÃ¹ng cho B4: sá»‘ lÆ°á»£ng dá»± phÃ²ng = VT cáº§n dÃ¹ng Ã· (28 Ã— sá»‘ ngÃ y nÃ y).',
        tracking=True,
    )
    ngay_du_tru_b5 = fields.Float(
        string='Sá»‘ ngÃ y (dá»± trá»¯)',
        default=20.0,
        digits=(16, 2),
        help='DÃ¹ng cho B5: sá»‘ lÆ°á»£ng dá»± trá»¯ tá»‘i thiá»ƒu = VT cáº§n dÃ¹ng Ã· (28 Ã— sá»‘ ngÃ y nÃ y).',
        tracking=True,
    )

    ke_hoach_kinh_doanh_ids = fields.One2many('ke.hoach.kinh.doanh', 'period_id', string='Káº¿ hoáº¡ch kinh doanh')
    ke_hoach_san_xuat_ids = fields.One2many('ke.hoach.san.xuat', 'period_id', string='Káº¿ hoáº¡ch sáº£n xuáº¥t')
    ke_hoach_vat_tu_line_ids = fields.One2many('ke.hoach.vat.tu.line', 'period_id', string='Káº¿ hoáº¡ch váº­t tÆ°')
    dinh_muc_ids = fields.One2many('dinh.muc', 'period_id', string='Äá»‹nh má»©c thÃ¡ng')
    tinh_toan_vat_tu_ids = fields.One2many('tinh.toan.vat.tu', 'period_id', string='TÃ­nh toÃ¡n váº­t tÆ°')
    tong_hop_vat_tu_ids = fields.One2many('tong.hop.vat.tu', 'period_id', string='Tá»•ng há»£p váº­t tÆ°')
    kh_dat_vat_tu_ids = fields.One2many('kh.dat.vat.tu', 'period_id', string='Káº¿ hoáº¡ch Ä‘áº·t váº­t tÆ°')

    ke_hoach_kinh_doanh_count = fields.Integer(compute='_compute_counts')
    ke_hoach_san_xuat_count = fields.Integer(compute='_compute_counts')
    ke_hoach_vat_tu_line_count = fields.Integer(compute='_compute_counts')
    dinh_muc_count = fields.Integer(compute='_compute_counts')
    tinh_toan_vat_tu_count = fields.Integer(compute='_compute_counts')
    tong_hop_vat_tu_count = fields.Integer(compute='_compute_counts')
    kh_dat_vat_tu_count = fields.Integer(compute='_compute_counts')
    month_ids_preview = fields.Char(
        string='CÃ¡c thÃ¡ng cÃ³ dá»¯ liá»‡u',
        compute='_compute_month_preview')

    _sql_constraints = [
        ('code_uniq', 'unique(code)', 'MÃ£ ká»³ pháº£i duy nháº¥t!'),
        ('company_month_uniq', 'unique(company_id, period_month)', 'CÃ´ng ty vÃ  thÃ¡ng báº¯t Ä‘áº§u khÃ´ng Ä‘Æ°á»£c trÃ¹ng!'),
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

    def _get_current_production_company(self):
        user_company = self.env.user.company_id
        if user_company.company_code in ('BNH', 'SSP'):
            return user_company
        raise UserError(_('CÃ´ng ty máº·c Ä‘á»‹nh cá»§a user khÃ´ng pháº£i cÃ´ng ty sáº£n xuáº¥t BNH/SSP. Vui lÃ²ng kiá»ƒm tra láº¡i cÃ´ng ty máº·c Ä‘á»‹nh cá»§a user trÆ°á»›c khi thao tÃ¡c káº¿ hoáº¡ch sáº£n xuáº¥t.'))



    def _build_period_code(self, company):
        company_key = re.sub(r'[^A-Za-z0-9]+', '', company.company_code or '') or str(company.id or 'CTY')
        prefix = 'KHVT_%s_' % company_key.upper()
        latest = self.sudo().search([('code', '=like', prefix + '%')], order='code desc', limit=1)
        next_no = 1
        if latest.code:
            try:
                next_no = int(latest.code.rsplit('_', 1)[-1]) + 1
            except (TypeError, ValueError):
                next_no = 1
        return '%s%04d' % (prefix, next_no)

    @api.model_create_multi
    def create(self, vals_list):
        Company = self.env['res.company']
        counters = {}
        for vals in vals_list:
            if not vals.get('code'):
                company = Company.browse(vals.get('company_id')) if vals.get('company_id') else self.env.company
                company_id = company.id or 0
                if company_id not in counters:
                    counters[company_id] = int(self._build_period_code(company).rsplit('_', 1)[-1])
                else:
                    counters[company_id] += 1
                company_key = re.sub(r'[^A-Za-z0-9]+', '', company.company_code or '') or str(company.id or 'CTY')
                vals['code'] = 'KHVT_%s_%04d' % (company_key.upper(), counters[company_id])
        return super().create(vals_list)

    @api.constrains('period_month')
    def _check_period_month(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.period_month and not pattern.match(rec.period_month):
                raise ValidationError('ThÃ¡ng báº¯t Ä‘áº§u pháº£i Ä‘Ãºng Ä‘á»‹nh dáº¡ng MM/YYYY, vÃ­ dá»¥ 04/2026.')

    @api.constrains('ngay_du_phong_b4', 'ngay_du_tru_b5')
    def _check_tham_so_ngay(self):
        for rec in self:
            if rec.ngay_du_phong_b4 is not False and rec.ngay_du_phong_b4 <= 0:
                raise ValidationError(
                    _('Sá»‘ ngÃ y B4 pháº£i lá»›n hÆ¡n 0 (Ä‘ang lÃ  %s).') % rec.ngay_du_phong_b4)
            if rec.ngay_du_tru_b5 is not False and rec.ngay_du_tru_b5 <= 0:
                raise ValidationError(
                    _('Sá»‘ ngÃ y B5 pháº£i lá»›n hÆ¡n 0 (Ä‘ang lÃ  %s).') % rec.ngay_du_tru_b5)

    @api.depends('ke_hoach_kinh_doanh_ids', 'ke_hoach_san_xuat_ids', 'ke_hoach_vat_tu_line_ids', 'dinh_muc_ids', 'tinh_toan_vat_tu_ids',
                 'tong_hop_vat_tu_ids', 'kh_dat_vat_tu_ids')
    def _compute_counts(self):
        for rec in self:
            rec.ke_hoach_kinh_doanh_count = len(rec.ke_hoach_kinh_doanh_ids)
            rec.ke_hoach_san_xuat_count = len(rec.ke_hoach_san_xuat_ids)
            rec.ke_hoach_vat_tu_line_count = len(rec.ke_hoach_vat_tu_line_ids)
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
    # Actions â€” gá»i tháº³ng SQL Procedure
    # ------------------------------------------------------------------

    def action_generate_b2(self):
        self.ensure_one()
        if not self.ke_hoach_vat_tu_line_ids:
            raise UserError(_('Chua co ke hoach vat tu. Vui long tao ke hoach vat tu tu ke hoach san xuat truoc khi sinh dinh muc.'))
        self.env.cr.execute('CALL public.fn_sinh_dinh_muc(%s)', (self.id,))
        self.state = 'dinh_muc'
        return self.action_open_step_b2()

    def _production_company_for_auto_seed(self):
        self.ensure_one()
        if self.ke_hoach_san_xuat_ids:
            return self.ke_hoach_san_xuat_ids[:1].company_id
        if self.env.user.company_id.company_code in ('BNH', 'SSP'):
            return self.env.user.company_id
        company = self.env['res.company'].sudo().search([('company_code', 'in', ('BNH', 'SSP'))], limit=1)
        if not company:
            raise UserError(_('Chua cau hinh cong ty san xuat BNH/SSP de tao ke hoach san xuat.'))
        return company

    def _sync_production_from_business(self):
        self.ensure_one()
        if not self.ke_hoach_kinh_doanh_ids:
            return
        Production = self.env['ke.hoach.san.xuat'].sudo()
        company = self._production_company_for_auto_seed()
        existing = {
            (line.company_id.id, line.ma_hang_id.id, line.ma_sap, line.month_key)
            for line in self.ke_hoach_san_xuat_ids
        }
        vals_list = []
        for line in self.ke_hoach_kinh_doanh_ids:
            key = (company.id, line.ma_hang_id.id, line.ma_sap, line.month_key)
            if key in existing:
                continue
            vals_list.append({
                'period_id': self.id,
                'company_id': company.id,
                'nganh_hang_id': line.nganh_hang_id.id,
                'dong_hang_id': line.dong_hang_id.id,
                'ma_hang_id': line.ma_hang_id.id,
                'ma_sap': line.ma_sap,
                'month_key': line.month_key,
                'month_date': line.month_date or self._month_key_to_date(line.month_key),
                'qty': line.qty,
                'note': line.note,
            })
        if vals_list:
            Production.with_context(is_importing=True).create(vals_list)

    def _prepare_material_plan_values_from_production(self):
        self.ensure_one()
        business_by_key = {
            (line.ma_hang_id.id, line.ma_sap, line.month_key): line
            for line in self.ke_hoach_kinh_doanh_ids
        }
        production_keys = {
            (line.ma_hang_id.id, line.ma_sap, line.month_key)
            for line in self.ke_hoach_san_xuat_ids
        }
        missing = sorted(set(business_by_key) - production_keys, key=lambda item: (item[1] or '', item[2] or ''))
        if missing:
            messages = []
            for key in missing[:20]:
                line = business_by_key[key]
                messages.append('Ma SAP=%s, Thang=%s' % (line.ma_sap or '', line.month_key or ''))
            if len(missing) > 20:
                messages.append('... con %s dong khac' % (len(missing) - 20))
            raise UserError(_('Ke hoach san xuat dang thieu dong so voi ke hoach kinh doanh:\n%s\nNeu khong san xuat, vui long giu dong va nhap So luong = 0.') % '\n'.join(messages))

        vals_list = []
        for line in self.ke_hoach_san_xuat_ids:
            key = (line.ma_hang_id.id, line.ma_sap, line.month_key)
            business_qty = business_by_key[key].qty if key in business_by_key else 0.0
            vals_list.append({
                'period_id': self.id,
                'company_id': line.company_id.id,
                'nganh_hang_id': line.nganh_hang_id.id,
                'dong_hang_id': line.dong_hang_id.id,
                'ma_hang_id': line.ma_hang_id.id,
                'ma_sap': line.ma_sap,
                'month_key': line.month_key,
                'month_date': line.month_date or self._month_key_to_date(line.month_key),
                'qty_kinh_doanh': business_qty,
                'qty_san_xuat': line.qty,
                'qty': line.qty,
                'note': line.note,
            })
        return vals_list

    def action_create_material_plan(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Ke hoach da sang buoc sau, khong the tao lai ke hoach vat tu.'))
        if not self.ke_hoach_san_xuat_ids:
            raise UserError(_('Chua co ke hoach san xuat de tao ke hoach vat tu.'))
        if self.ke_hoach_vat_tu_line_ids:
            raise UserError(_('Ke hoach vat tu da co du lieu. Vui long xoa du lieu cu neu can tao lai.'))
        vals_list = self._prepare_material_plan_values_from_production()
        if vals_list:
            self.env['ke.hoach.vat.tu.line'].sudo().with_context(skip_period_lock=True).create(vals_list)
        self.with_context(vat_tu_chatter_scope='vt').message_post(
            body=_('Da tao %s dong ke hoach vat tu tu ke hoach san xuat.') % len(vals_list)
        )
        return self.action_open_workflow_vt()
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
            period.with_context(vat_tu_chatter_scope='vt').message_post(
                body=_('%s Ä‘Ã£ reset vá» nhÃ¡p.') % self.env.user.name
            )
            period.dinh_muc_ids.unlink()
            period.tinh_toan_vat_tu_ids.unlink()
            period.tong_hop_vat_tu_ids.unlink()
            period.kh_dat_vat_tu_ids.unlink()
            period.state = 'ke_hoach'

    def _apply_plan_excel_style(self, ws, header_row, max_col):
        base_font = Font(name='Times New Roman', size=10)
        label_font = Font(name='Times New Roman', size=10, bold=True)
        value_font = Font(name='Times New Roman', size=10)
        header_font = Font(name='Times New Roman', size=10, bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='3F6F8F')
        thin_side = Side(style='thin', color='B7C6D0')
        header_side = Side(style='thin', color='2F556D')
        meta_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
        header_border = Border(left=header_side, right=header_side, top=header_side, bottom=header_side)
        header_alignment = Alignment(horizontal='center', vertical='center')
        body_alignment = Alignment(vertical='center')

        for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, header_row), min_col=1, max_col=max_col):
            for cell in row:
                cell.font = base_font
                cell.alignment = body_alignment

        for row_idx in (1, 2, 3):
            label_cell = ws.cell(row=row_idx, column=1)
            value_cell = ws.cell(row=row_idx, column=2)
            label_cell.font = label_font
            value_cell.font = value_font
            label_cell.border = meta_border
            label_cell.alignment = Alignment(horizontal='left', vertical='center')
            value_cell.alignment = Alignment(horizontal='left', vertical='center')
            for col_idx in range(2, max_col + 1):
                meta_cell = ws.cell(row=row_idx, column=col_idx)
                meta_cell.border = meta_border
                meta_cell.font = value_font
                meta_cell.alignment = Alignment(horizontal='left', vertical='center')

        for cell in ws[header_row][:max_col]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = header_border
            cell.alignment = header_alignment

        ws.row_dimensions[header_row].height = 22
        ws.freeze_panes = ws.cell(row=header_row + 1, column=1).coordinate

    def _write_plan_metadata(self, ws):
        ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=5)
        ws.merge_cells(start_row=2, start_column=2, end_row=2, end_column=5)
        ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=5)
        ws.cell(row=1, column=1, value='MÃ£')
        ws.cell(row=1, column=2, value=self.code or '')
        ws.cell(row=2, column=1, value='ThÃ¡ng báº¯t Ä‘áº§u')
        ws.cell(row=2, column=2, value=self.period_month or '')
        ws.cell(row=3, column=1, value='CÃ´ng ty')
        ws.cell(row=3, column=2, value=self.company_id.name or '')

    def _protect_plan_sheet(self, ws, header_row, unlocked_cols):
        for row in ws.iter_rows(min_row=1, max_row=max(ws.max_row, header_row + 100), min_col=1, max_col=ws.max_column):
            for cell in row:
                cell.protection = Protection(locked=True)
        for row_idx in range(header_row + 1, max(ws.max_row, header_row + 100) + 1):
            for col_idx in unlocked_cols:
                ws.cell(row=row_idx, column=col_idx).protection = Protection(locked=False)
        ws.protection.sheet = True

    def _xlsx_download_action(self, wb, filename):
        output = io.BytesIO()
        wb.save(output)
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
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

    def action_download_b1_template(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Káº¿ hoáº¡ch Ä‘Ã£ sang bÆ°á»›c sau, khÃ´ng thá»ƒ táº£i template Ä‘á»ƒ import láº¡i.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Báº¡n khÃ´ng cÃ³ quyá»n táº£i template káº¿ hoáº¡ch kinh doanh.'))

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach kinh doanh'
        self._write_plan_metadata(ws)
        headers = ['NgÃ nh hÃ ng', 'DÃ²ng hÃ ng', 'MÃ£ hÃ ng', 'MÃ£ SAP']
        headers += ['ThÃ¡ng %s' % (self.period_month or '')]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)
        self._apply_plan_excel_style(ws, header_row, len(headers))
        ws.column_dimensions['A'].width = 18
        ws.column_dimensions['B'].width = 22
        ws.column_dimensions['C'].width = 24
        ws.column_dimensions['D'].width = 24
        ws.column_dimensions['E'].width = 16
        return self._xlsx_download_action(
            wb,
            'KHKD_%s.xlsx' % (self.code),
        )

    def action_open_import_kinh_doanh_wizard(self):
        self.ensure_one()
        if self.state != 'ke_hoach':
            raise UserError(_('Káº¿ hoáº¡ch kinh doanh Ä‘Ã£ khÃ³a vÃ¬ ká»³ káº¿ hoáº¡ch Ä‘Ã£ sang bÆ°á»›c sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Báº¡n khÃ´ng cÃ³ quyá»n import káº¿ hoáº¡ch kinh doanh.'))
        return {
            'name': _('Import káº¿ hoáº¡ch kinh doanh'),
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
            raise UserError(_('Káº¿ hoáº¡ch sáº£n xuáº¥t Ä‘Ã£ khÃ³a vÃ¬ ká»³ káº¿ hoáº¡ch Ä‘Ã£ sang bÆ°á»›c sau.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Báº¡n khÃ´ng cÃ³ quyá»n import káº¿ hoáº¡ch sáº£n xuáº¥t.'))
        return {
            'name': _('Import káº¿ hoáº¡ch sáº£n xuáº¥t'),
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
            raise UserError(_('Káº¿ hoáº¡ch Ä‘Ã£ sang bÆ°á»›c sau, khÃ´ng thá»ƒ export láº¡i cho sáº£n xuáº¥t.'))
        if not (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu') or
            self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        ):
            raise UserError(_('Báº¡n khÃ´ng cÃ³ quyá»n export káº¿ hoáº¡ch cho sáº£n xuáº¥t.'))
        lines = self.ke_hoach_san_xuat_ids.sorted(lambda r: (
            r.nganh_hang_id.name or '',
            r.dong_hang_id.name or '',
            r.ma_hang_id.code or '',
            r.ma_sap or '',
            r.month_date or date.min,
        ))
        if not lines:
            raise UserError(_('Chua co ke hoach san xuat de export.'))

        months = sorted(
            {line.month_key for line in lines if line.month_key},
            key=lambda month: self._month_key_to_date(month) or date.min,
        )

        wb = Workbook()
        ws = wb.active
        ws.title = 'Ke hoach san xuat'
        self._write_plan_metadata(ws)
        headers = ['NgÃ nh hÃ ng', 'DÃ²ng hÃ ng', 'MÃ£ hÃ ng', 'MÃ£ SAP']
        headers += ['ThÃ¡ng %s' % month for month in months]
        header_row = 6
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=header_row, column=col_idx, value=label)

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
            ws.append(list(key) + [qty_by_month.get(month, 0.0) for month in months])

        self._apply_plan_excel_style(ws, header_row, len(headers))

        month_col_indexes = list(range(5, 5 + len(months)))
        self._protect_plan_sheet(ws, header_row, month_col_indexes)

        for col_idx in range(1, len(headers) + 1):
            max_len = max(len(str(ws.cell(row=row_idx, column=col_idx).value or '')) for row_idx in range(1, ws.max_row + 1))
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 2, 12), 28)
        ws.column_dimensions['A'].width = 22
        ws.column_dimensions['B'].width = 22
        ws.column_dimensions['C'].width = 24
        ws.column_dimensions['D'].width = 24

        return self._xlsx_download_action(
            wb,
            'KHSX_%s.xlsx' % (self.code or self.id),
        )

    def _action_open_step(self, view_xmlid, context=None):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Káº¿ hoáº¡ch váº­t tÆ°'),
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(view_xmlid).id, 'form')],
            'target': 'current',
            'context': context or {},
        }

    def action_open_workflow_sx(self):
        return self._action_open_step(
            'sonha_vat_tu.view_ke_hoach_vat_tu_form_sx',
            context={
                'form_view_ref': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_sx',
                'vat_tu_chatter_scope': 'sx',
            },
        )

    def action_open_workflow_vt(self):
        return self._action_open_step(
            'sonha_vat_tu.view_ke_hoach_vat_tu_form_vt',
            context={
                'form_view_ref': 'sonha_vat_tu.view_ke_hoach_vat_tu_form_vt',
                'vat_tu_chatter_scope': 'vt',
            },
        )

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

