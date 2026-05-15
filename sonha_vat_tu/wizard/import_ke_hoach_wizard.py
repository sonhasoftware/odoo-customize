# -*- coding: utf-8 -*-
import base64
import io
import re
from datetime import date

from markupsafe import Markup
from openpyxl import load_workbook

from odoo import fields, models, _
from odoo.exceptions import UserError


class ImportKeHoachWizard(models.TransientModel):
    _name = 'import.ke.hoach.wizard'
    _description = 'Import ke hoach tu Excel'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Ky',
        default=lambda self: self.env.context.get('active_id'))
    import_type = fields.Selection([
        ('business', 'Kế hoạch kinh doanh'),
        ('production', 'Kế hoạch sản xuất'),
    ], string='Loại import', required=True,
        default=lambda self: self.env.context.get('default_import_type', 'business'))
    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Ten file')

    MONTH_RE = re.compile(r'(\d{1,2})\s*[/\-]\s*(\d{4})')

    def _parse_month_header(self, label):
        if not label:
            return None
        m = self.MONTH_RE.search(str(label))
        if not m:
            return None
        try:
            month = int(m.group(1))
            year = int(m.group(2))
            date(year, month, 1)
            return f'{month:02d}/{year}'
        except ValueError:
            return None

    def _find_master(self, model, raw):
        Model = self.env[model].sudo()
        raw = (raw or '').strip()
        if not raw:
            return Model.browse()
        rec = Model.search(['|', ('code', '=', raw), ('name', '=', raw)], limit=1)
        if not rec:
            rec = Model.search([('name', 'ilike', raw)], limit=1)
        return rec

    def _find_production_company(self, raw):
        raw = str(raw or '').strip()
        if not raw:
            return self.env['res.company'].browse()
        Company = self.env['res.company'].sudo()
        company = Company.search([('name', '=', raw)], limit=1)
        if not company:
            company = Company.search([('company_code', '=', raw)], limit=1)
        if not company:
            company = Company.search([('name', 'ilike', raw)], limit=1)
        if company.company_code not in ('BNH', 'SSP'):
            return self.env['res.company'].browse()
        return company

    def _read_workbook(self):
        if not self.file_data:
            raise UserError(_('Vui lòng chọn file Excel.'))
        try:
            wb = load_workbook(
                io.BytesIO(base64.b64decode(self.file_data)),
                data_only=True,
                read_only=True,
            )
        except Exception as exc:
            raise UserError(_('Không đọc được file Excel: %s') % exc)
        rows = [tuple(row) for row in wb.active.iter_rows(values_only=True)]
        if not rows:
            raise UserError(_('File rỗng.'))
        return rows

    def _prepare_rows(self, rows):
        header = [str(c).strip() if c is not None else '' for c in rows[0]]
        month_cols = []
        company_col_idx = None
        for idx, label in enumerate(header):
            month_key = self._parse_month_header(label)
            if month_key and idx >= 4:
                month_cols.append((idx, month_key))
            if str(label).strip().lower() in (
                'đơn vị sản xuất',
                'don vi san xuat',
                'cong ty san xuat',
                'công ty sản xuất',
            ):
                company_col_idx = idx
        if not month_cols:
            raise UserError(_('Không tìm thấy cột tháng nào trong file.'))
        if self.import_type == 'production' and company_col_idx is None:
            raise UserError(_('File sản xuất thiếu cột "Đơn vị sản xuất".'))
        return header, month_cols, company_col_idx

    def _validate_master_row(self, row_idx, row, errors):
        NganhHang = self.env['nganh.hang'].sudo()
        DongHang = self.env['dong.hang'].sudo()
        MaHang = self.env['ma.hang'].sudo()

        nganh_raw = str(row[0]).strip() if row[0] not in (None, '') else ''
        dong_raw = str(row[1]).strip() if row[1] not in (None, '') else ''
        ma_hang = str(row[2]).strip() if row[2] not in (None, '') else ''
        ma_sap = str(row[3]).strip() if row[3] not in (None, '') else ''

        if not nganh_raw:
            errors.append(_('Dòng %d: thiếu Ngành hàng.') % row_idx)
            return None
        if not dong_raw:
            errors.append(_('Dòng %d: thiếu Dòng hàng.') % row_idx)
            return None
        if not ma_hang:
            errors.append(_('Dòng %d: thiếu Mã hàng.') % row_idx)
            return None
        if not ma_sap:
            errors.append(_('Dòng %d: thiếu Mã SAP.') % row_idx)
            return None

        nganh = self._find_master('nganh.hang', nganh_raw)
        if not nganh:
            errors.append(_('Dòng %d: Ngành hàng "%s" không có trong danh mục.') % (row_idx, nganh_raw))
            return None
        dong = self._find_master('dong.hang', dong_raw)
        if not dong:
            errors.append(_('Dòng %d: Dòng hàng "%s" không có trong danh mục.') % (row_idx, dong_raw))
            return None
        if dong.nganh_hang_id != nganh:
            errors.append(_('Dòng %d: Dòng hàng "%s" không thuộc ngành "%s".') % (row_idx, dong_raw, nganh_raw))
            return None

        ma_hang_rec = MaHang.search([('code', '=', ma_hang), ('ma_sap', '=', ma_sap)], limit=1)
        if not ma_hang_rec:
            errors.append(_('Dòng %d: Mã hàng "%s" và Mã SAP "%s" không khớp danh mục.') % (row_idx, ma_hang, ma_sap))
            return None
        if ma_hang_rec.dong_hang_id != dong:
            errors.append(_('Dòng %d: Mã hàng "%s" không thuộc dòng hàng "%s".') % (row_idx, ma_hang, dong_raw))
            return None

        return {
            'nganh_hang_id': nganh.id,
            'dong_hang_id': dong.id,
            'ma_hang_id': ma_hang_rec.id,
            'ma_sap': ma_sap,
        }

    def _raise_errors(self, errors):
        if not errors:
            return
        shown = errors[:80]
        msg = '\n'.join('- %s' % error for error in shown)
        if len(errors) > 80:
            msg += _('\n... còn %d lỗi khác.') % (len(errors) - 80)
        raise UserError(_('File import có lỗi, chưa ghi dữ liệu:\n%s') % msg)

    def action_import(self):
        self.ensure_one()
        if not self.period_id:
            raise UserError(_('Thiếu kỳ kế hoạch.'))
        if self.period_id.state != 'ke_hoach':
            raise UserError(_('Kỳ kế hoạch đã sang bước sau, không thể import lại kế hoạch.'))
        is_supply = self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu')
        is_department = self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu')
        is_manager = self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        if self.import_type == 'business' and not (is_supply or is_manager):
            raise UserError(_('Bạn không có quyền import kế hoạch kinh doanh.'))
        if self.import_type == 'production' and not (is_department or is_manager):
            raise UserError(_('Bạn không có quyền import kế hoạch sản xuất.'))

        rows = self._read_workbook()
        header, month_cols, company_col_idx = self._prepare_rows(rows)

        if self.import_type == 'business':
            count = self._import_business(rows, header, month_cols)
            label = 'kế hoạch kinh doanh'
        else:
            count = self._import_production(rows, header, month_cols, company_col_idx)
            label = 'kế hoạch sản xuất'

        attachment = self.env['ir.attachment'].sudo().create({
            'name': self.file_name or 'ke_hoach_import.xlsx',
            'type': 'binary',
            'datas': self.file_data,
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.period_id.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        self.period_id.message_post(body=Markup(
            '<p><b>Đã import %s dòng %s từ file %s.</b></p>' %
            (count, label, self.file_name or '-')
        ), attachment_ids=[attachment.id])
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.period_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b1').id, 'form')],
            'target': 'current',
        }

    def _import_business(self, rows, header, month_cols):
        Plan = self.env['ke.hoach.kinh.doanh'].sudo()
        Period = self.env['ke.hoach.vat.tu']
        vals_list = []
        errors = []
        seen = set()

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            base_vals = self._validate_master_row(row_idx, row, errors)
            if not base_vals:
                continue
            for col_idx, month_key in month_cols:
                raw_qty = row[col_idx]
                if raw_qty in (None, '', 0, 0.0):
                    continue
                try:
                    qty = float(raw_qty)
                except (TypeError, ValueError):
                    errors.append(_('Dòng %d, tháng %s: "%s" không phải số.') % (row_idx, month_key, raw_qty))
                    continue
                key = (base_vals['ma_sap'], month_key)
                if key in seen:
                    errors.append(_('Dòng %d: trùng Mã SAP=%s, Tháng=%s trong file.') % (row_idx, base_vals['ma_sap'], month_key))
                    continue
                seen.add(key)
                vals = dict(base_vals)
                vals.update({
                    'period_id': self.period_id.id,
                    'month_key': month_key,
                    'month_date': Period._month_key_to_date(month_key),
                    'qty': qty,
                })
                vals_list.append(vals)

        existing = {
            (line.ma_sap, line.month_key)
            for line in Plan.search([('period_id', '=', self.period_id.id)])
        }
        for vals in vals_list:
            if (vals['ma_sap'], vals['month_key']) in existing:
                errors.append(_('Đã tồn tại kế hoạch kinh doanh Mã SAP=%s, Tháng=%s.') % (vals['ma_sap'], vals['month_key']))
        self._raise_errors(errors)
        if vals_list:
            Plan.with_context(is_importing=True).create(vals_list)
        return len(vals_list)

    def _import_production(self, rows, header, month_cols, company_col_idx):
        Plan = self.env['ke.hoach.san.xuat'].sudo()
        Period = self.env['ke.hoach.vat.tu']
        vals_by_key = {}
        errors = []

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            base_vals = self._validate_master_row(row_idx, row, errors)
            if not base_vals:
                continue
            company = self._find_production_company(row[company_col_idx])
            if not company:
                errors.append(_('Dòng %d: Đơn vị sản xuất không thuộc công ty BNH/SSP.') % row_idx)
                continue
            for col_idx, month_key in month_cols:
                raw_qty = row[col_idx]
                if raw_qty in (None, '', 0, 0.0):
                    continue
                try:
                    qty = float(raw_qty)
                except (TypeError, ValueError):
                    errors.append(_('Dòng %d, tháng %s: "%s" không phải số.') % (row_idx, month_key, raw_qty))
                    continue
                key = (company.id, base_vals['ma_sap'], month_key)
                if key in vals_by_key:
                    vals_by_key[key]['qty'] += qty
                    continue
                vals = dict(base_vals)
                vals.update({
                    'period_id': self.period_id.id,
                    'company_id': company.id,
                    'month_key': month_key,
                    'month_date': Period._month_key_to_date(month_key),
                    'qty': qty,
                })
                vals_by_key[key] = vals

        self._raise_errors(errors)
        vals_list = list(vals_by_key.values())
        for vals in vals_list:
            existing = Plan.search([
                ('period_id', '=', self.period_id.id),
                ('company_id', '=', vals['company_id']),
                ('ma_sap', '=', vals['ma_sap']),
                ('month_key', '=', vals['month_key']),
            ], limit=1)
            if existing:
                existing.with_context(is_importing=True).write(vals)
            else:
                Plan.with_context(is_importing=True).create(vals)
        return len(vals_list)
