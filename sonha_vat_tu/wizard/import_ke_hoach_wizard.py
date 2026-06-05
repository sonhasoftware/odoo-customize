# -*- coding: utf-8 -*-
import base64
import io
import re
import unicodedata
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

    def _norm_text(self, value):
        return str(value or '').strip()

    def _norm_compare(self, value):
        text = unicodedata.normalize('NFD', self._norm_text(value).lower())
        text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
        return re.sub(r'\s+', ' ', text).strip()

    def _validate_metadata(self, rows):
        if len(rows) < 6:
            raise UserError(_('File Excel không đúng mẫu. Vui lòng tải lại template từ kỳ kế hoạch đang mở.'))

        meta = {}
        for row_idx in range(3):
            row = rows[row_idx] if row_idx < len(rows) else ()
            label = self._norm_text(row[0] if len(row) > 0 else '')
            value = self._norm_text(row[1] if len(row) > 1 else '')
            meta[label.lower()] = value

        code = meta.get('mã') or meta.get('ma')
        month = meta.get('tháng bắt đầu') or meta.get('thang bat dau')
        company = meta.get('công ty') or meta.get('cong ty')

        errors = []
        if not code:
            errors.append(_('Mã kỳ không được để trống. Vui lòng kiểm tra ô B1.'))
        elif code != (self.period_id.code or ''):
            errors.append(_('Mã kỳ trong file là "%s", không đúng với kỳ đang mở "%s".') % (code, self.period_id.code or ''))

        if not month:
            errors.append(_('Tháng bắt đầu không được để trống. Vui lòng kiểm tra ô B2.'))
        elif month != (self.period_id.period_month or ''):
            errors.append(_('Tháng bắt đầu trong file là "%s", không đúng với kỳ đang mở "%s".') % (month, self.period_id.period_month or ''))

        if not company:
            errors.append(_('Công ty không được để trống. Vui lòng kiểm tra ô B3.'))
        elif company != (self.period_id.company_id.name or ''):
            errors.append(_('Công ty trong file là "%s", không đúng với kỳ đang mở "%s".') % (company, self.period_id.company_id.name or ''))

        self._raise_errors(errors)

    def _prepare_rows(self, rows):
        header_row_idx = 5
        header = [str(c).strip() if c is not None else '' for c in rows[header_row_idx]]
        month_cols = []
        for idx, label in enumerate(header):
            month_key = self._parse_month_header(label)
            if month_key and idx >= 4:
                month_cols.append((idx, month_key))
        if not month_cols:
            raise UserError(_('Không tìm thấy cột tháng trong bảng dữ liệu. Vui lòng kiểm tra dòng tiêu đề số 6.'))
        return header, month_cols, header_row_idx + 1

    def _validate_master_row(self, row_idx, row, errors):
        MaHang = self.env['ma.hang'].sudo()

        nganh_raw = str(row[0]).strip() if row[0] not in (None, '') else ''
        dong_raw = str(row[1]).strip() if row[1] not in (None, '') else ''
        ma_sap = str(row[3]).strip() if row[3] not in (None, '') else ''

        if not nganh_raw:
            errors.append(_('Dòng %d: thiếu Ngành hàng.') % row_idx)
            return None
        if not ma_sap:
            errors.append(_('Dòng %d: thiếu Mã SAP/Mã đơn vị.') % row_idx)
            return None

        ma_hang_rec = MaHang.search([('ma_sap', '=', ma_sap)], limit=1)
        if not ma_hang_rec:
            errors.append(_('Dòng %d: Mã SAP/Mã đơn vị "%s" không có trong danh mục mã hàng.') % (row_idx, ma_sap))
            return None
        if not ma_hang_rec.nganh_hang:
            errors.append(_('Dòng %d: Mã SAP/Mã đơn vị "%s" chưa có Ngành hàng từ MDM.') % (row_idx, ma_sap))
            return None
        if self._norm_compare(nganh_raw) != self._norm_compare(ma_hang_rec.nganh_hang):
            errors.append(_(
                'Dòng %d: Ngành hàng "%s" không khớp MDM của Mã SAP/Mã đơn vị "%s" ("%s").'
            ) % (row_idx, nganh_raw, ma_sap, ma_hang_rec.nganh_hang))
            return None

        return {
            'nganh_hang': ma_hang_rec.nganh_hang or nganh_raw,
            'dong_hang': dong_raw,
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
        raise UserError(_('File Excel có lỗi, chưa ghi dữ liệu:\n%s') % msg)

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
        self._validate_metadata(rows)
        header, month_cols, data_start_idx = self._prepare_rows(rows)

        if self.import_type == 'business':
            count = self._import_business(rows, header, month_cols, data_start_idx)
            label = 'kế hoạch kinh doanh'
        else:
            count = self._import_production(rows, header, month_cols, data_start_idx)
            label = 'kế hoạch sản xuất'

        attachment = self.env['ir.attachment'].sudo().create({
            'name': self.file_name or 'ke_hoach_import.xlsx',
            'type': 'binary',
            'datas': self.file_data,
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.period_id.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        scope = 'kd' if self.import_type == 'business' else 'sx'
        self.period_id.with_context(vat_tu_chatter_scope=scope).message_post(body=Markup(
            '<p><b>Đã import %s dòng %s từ file %s.</b></p>' %
            (count, label, self.file_name or '-')
        ), attachment_ids=[attachment.id])
        view_xmlid = (
            'sonha_vat_tu.view_ke_hoach_vat_tu_form_kd'
            if self.import_type == 'business'
            else 'sonha_vat_tu.view_ke_hoach_vat_tu_form_sx'
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.period_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref(view_xmlid).sudo().id, 'form')],
            'context': {'vat_tu_chatter_scope': scope},
            'target': 'current',
        }

    def _import_business(self, rows, header, month_cols, data_start_idx):
        Plan = self.env['ke.hoach.kinh.doanh'].sudo()
        Period = self.env['ke.hoach.vat.tu']
        vals_list = []
        errors = []
        seen = set()

        for row_idx, row in enumerate(rows[data_start_idx:], start=data_start_idx + 1):
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
            self.period_id._sync_production_from_business()
        return len(vals_list)

    def _import_production(self, rows, header, month_cols, data_start_idx):
        Plan = self.env['ke.hoach.san.xuat'].sudo()
        Period = self.env['ke.hoach.vat.tu']
        vals_by_key = {}
        errors = []
        company = self.env.user.company_id
        if company.company_code not in ('BNH', 'SSP'):
            raise UserError(_('Công ty hiện tại không phải công ty sản xuất BNH/SSP. Vui lòng chọn đúng công ty trước khi import kế hoạch sản xuất.'))

        for row_idx, row in enumerate(rows[data_start_idx:], start=data_start_idx + 1):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            base_vals = self._validate_master_row(row_idx, row, errors)
            if not base_vals:
                continue
            for col_idx, month_key in month_cols:
                raw_qty = row[col_idx]
                if raw_qty in (None, ''):
                    continue
                try:
                    qty = float(raw_qty)
                except (TypeError, ValueError):
                    errors.append(_('Dòng %d, tháng %s: "%s" không phải số.') % (row_idx, month_key, raw_qty))
                    continue
                key = (company.id, base_vals['ma_hang_id'], base_vals['ma_sap'], month_key)
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
        business_keys = {
            (line.ma_hang_id.id, line.ma_sap, line.month_key): line
            for line in self.period_id.ke_hoach_kinh_doanh_ids
        }
        imported_keys = {
            (vals['ma_hang_id'], vals['ma_sap'], vals['month_key'])
            for vals in vals_list
        }
        missing = sorted(set(business_keys) - imported_keys, key=lambda item: (item[1] or '', item[2] or ''))
        if missing:
            for key in missing[:20]:
                line = business_keys[key]
                errors.append(_('Thiếu dòng kế hoạch kinh doanh Mã SAP=%s, Tháng=%s. Nếu không sản xuất, vui lòng giữ dòng và nhập Số lượng = 0.') % (line.ma_sap, line.month_key))
            if len(missing) > 20:
                errors.append(_('... còn %d dòng kế hoạch kinh doanh bị thiếu.') % (len(missing) - 20))
        self._raise_errors(errors)
        Plan.search([('period_id', '=', self.period_id.id)]).with_context(is_importing=True).unlink()
        if vals_list:
            Plan.with_context(is_importing=True).create(vals_list)
        return len(vals_list)
