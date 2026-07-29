# -*- coding: utf-8 -*-
import re
from datetime import date, datetime

from openpyxl import Workbook

from odoo import _, fields, models
from odoo.exceptions import UserError

TEMPLATE_HEADERS = ['Đơn vị', 'Mã NVL', 'Tên NVL', 'Tháng', 'Số lượng']
TEMPLATE_WIDTHS = [14, 26, 36, 14, 16]


class ImportVatTuDiDuongWizard(models.TransientModel):
    _name = 'import.vat.tu.di.duong.wizard'
    _description = 'Import vật tư đi đường'
    _inherit = ['vat.tu.excel.mixin']

    TEMPLATE_SHEET_NAME = 'Vat tu di duong'
    DATA_START_ROW = 2
    # A=Đơn vị, B=Mã NVL, C=Tên NVL (tùy chọn), D=Tháng, E=Số lượng
    COL_COMPANY, COL_MA_NVL, COL_TEN_NVL, COL_MONTH, COL_QTY = range(5)

    MONTH_RE = re.compile(r'(\d{1,2})\s*[/\-]\s*(\d{4})')

    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')
    period_id = fields.Many2one(
        'ke.hoach.vat.tu',
        string='Kỳ kế hoạch',
        readonly=True,
        default=lambda self: self.env.context.get('default_period_id') or self.env.context.get('active_id'),
    )

    def _parse_month(self, value):
        if isinstance(value, (date, datetime)):
            return value.strftime('%m/%Y'), date(value.year, value.month, 1)
        match = self.MONTH_RE.search(str(value or '').strip())
        if not match:
            return False, False
        month, year = int(match.group(1)), int(match.group(2))
        try:
            return '%02d/%d' % (month, year), date(year, month, 1)
        except ValueError:
            return False, False

    def _format_month_display(self, value):
        if value in (None, ''):
            return ''
        if isinstance(value, (date, datetime)):
            return value.strftime('%d/%m/%Y')
        return str(value).strip()

    def action_download_template(self):
        self.ensure_one()
        wb = Workbook()
        ws = wb.active
        ws.title = self.TEMPLATE_SHEET_NAME
        for col_idx, label in enumerate(TEMPLATE_HEADERS, start=1):
            ws.cell(row=1, column=col_idx, value=label)
        self._style_excel_header(ws, len(TEMPLATE_HEADERS))
        self._apply_company_code_validation(wb, ws)
        self._set_excel_widths(ws, TEMPLATE_WIDTHS)
        return self._xlsx_download_action(wb, 'Template_vat_tu_di_duong.xlsx')

    def _parse_rows(self, rows, company_by_code):
        """Đọc + kiểm tra toàn bộ file, trả về danh sách vals đã hợp lệ."""
        errors = []
        parsed = []
        seen_keys = set()

        for row_number, row in enumerate(rows, start=self.DATA_START_ROW):
            if not any(cell not in (None, '') for cell in row):
                continue

            company_code = str(self._cell(row, self.COL_COMPANY) or '').strip()
            ma_nvl = self._normalize_ma_nvl(self._cell(row, self.COL_MA_NVL))
            ten_nvl = str(self._cell(row, self.COL_TEN_NVL) or '').strip()
            month_raw = self._cell(row, self.COL_MONTH)
            month_key, month_date = self._parse_month(month_raw)

            row_errors = []
            if not company_code:
                row_errors.append(_('Dòng %d: thiếu Đơn vị.') % row_number)
            if not ma_nvl:
                row_errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)
            if not month_key:
                month_display = self._format_month_display(month_raw)
                row_errors.append(
                    _('Dòng %d: Tháng "%s" không đúng định dạng MM/YYYY.') % (row_number, month_display)
                    if month_display else _('Dòng %d: thiếu Tháng.') % row_number
                )

            so_luong = 0.0
            try:
                so_luong = self._parse_number(self._cell(row, self.COL_QTY))
                if so_luong < 0:
                    row_errors.append(_('Dòng %d: Số lượng không được âm.') % row_number)
            except UserError as exc:
                row_errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))

            company = company_by_code.get(company_code) if company_code else False
            if company_code and not company:
                row_errors.append(_('Dòng %d: Đơn vị "%s" không tồn tại.') % (row_number, company_code))

            if company_code and ma_nvl and month_key:
                dup_key = (company_code, ma_nvl, month_key)
                if dup_key in seen_keys:
                    row_errors.append(
                        _('Dòng %d: trùng Đơn vị + Mã NVL + Tháng trong file.') % row_number)
                else:
                    seen_keys.add(dup_key)

            if row_errors:
                errors.extend(row_errors)
                continue

            parsed.append({
                'company_id': company.id,
                'ma_nvl': ma_nvl,
                'ten_nvl': ten_nvl or False,
                'month_key': month_key,
                'month_date': month_date,
                'so_luong': so_luong,
            })

        self._raise_import_errors(errors)
        return parsed

    def _apply_rows(self, parsed):
        """Ghi dữ liệu: 1 query tra dòng cũ, 1 insert, 1 update — không tra
        từng dòng như trước."""
        VatTuDiDuong = self.env['vat.tu.di.duong'].sudo()
        if not parsed:
            return 0, 0

        existing = VatTuDiDuong.search([
            ('company_id', 'in', list({v['company_id'] for v in parsed})),
            ('ma_nvl', 'in', list({v['ma_nvl'] for v in parsed})),
            ('month_key', 'in', list({v['month_key'] for v in parsed})),
        ])
        existing_map = {
            (line.company_id.id, line.ma_nvl, line.month_key): line.id
            for line in existing
        }

        to_create = []
        update_ids, update_names, update_qtys = [], [], []
        for vals in parsed:
            line_id = existing_map.get((vals['company_id'], vals['ma_nvl'], vals['month_key']))
            if line_id:
                update_ids.append(line_id)
                update_names.append(vals['ten_nvl'] or '')
                update_qtys.append(vals['so_luong'])
            else:
                to_create.append(vals)

        if update_ids:
            self.env.cr.execute("""
                UPDATE vat_tu_di_duong AS v SET
                    ten_nvl = COALESCE(NULLIF(data.ten_nvl, ''), v.ten_nvl),
                    so_luong = data.so_luong,
                    write_uid = %s,
                    write_date = NOW() AT TIME ZONE 'UTC'
                FROM (
                    SELECT unnest(%s::int[]) AS id,
                           unnest(%s::varchar[]) AS ten_nvl,
                           unnest(%s::numeric[]) AS so_luong
                ) AS data
                WHERE v.id = data.id
            """, [self.env.uid, update_ids, update_names, update_qtys])
            VatTuDiDuong.browse(update_ids).invalidate_recordset(
                ['ten_nvl', 'so_luong', 'write_uid', 'write_date'])
        if to_create:
            VatTuDiDuong.create(to_create)

        return len(to_create), len(update_ids)

    def action_import(self):
        self.ensure_one()
        rows = self._read_data_rows()
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu (từ dòng 2).'))

        parsed = self._parse_rows(rows, self._company_by_code())
        created, updated = self._apply_rows(parsed)

        parts = []
        if created:
            parts.append(_('thêm %d dòng mới') % created)
        if updated:
            parts.append(_('cập nhật %d dòng') % updated)
        message = (
            _('Import thành công: %s.') % ', '.join(parts) if parts
            else _('Không có dữ liệu hợp lệ để import.')
        )

        next_action = None
        if self.period_id:
            if created or updated:
                self.period_id.write({'vat_tu_di_duong_imported': True})
            next_action = {
                'type': 'ir.actions.act_window',
                'res_model': 'ke.hoach.vat.tu',
                'res_id': self.period_id.id,
                'view_mode': 'form',
                'views': [(self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_b3').id, 'form')],
                'target': 'current',
            }

        return self._notify_and_close(
            _('Import vật tư đi đường'), message,
            success=bool(created or updated), next_action=next_action,
        )
