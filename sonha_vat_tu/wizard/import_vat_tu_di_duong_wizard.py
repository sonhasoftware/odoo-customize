# -*- coding: utf-8 -*-
import base64
import io
import re
import warnings
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

from odoo import _, fields, models
from odoo.exceptions import UserError


class ImportVatTuDiDuongWizard(models.TransientModel):
    _name = 'import.vat.tu.di.duong.wizard'
    _description = 'Import vật tư đi đường'

    TEMPLATE_SHEET_NAME = 'Vat tu di duong'
    DATA_START_ROW = 2
    # A=Đơn vị, B=Số PR, C=Mã NVL, D=Tên NVL (bỏ qua nếu trống), E=Tháng, F=Số lượng
    COL_COMPANY, COL_PR, COL_MA_NVL, COL_TEN_NVL, COL_MONTH, COL_QTY = range(6)

    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')
    nguon = fields.Selection(
        selection=[
            ('bcu', 'Ban cung ứng'),
            ('don_vi', 'Đơn vị'),
        ],
        string='Nguồn dữ liệu',
        required=True,
        default='bcu',
        help='BCU: dùng cho tính toán B4/B5. Đơn vị: chỉ đối chiếu trên B4.',
    )

    MONTH_RE = re.compile(r'(\d{1,2})\s*[/\-]\s*(\d{4})')

    def _cell(self, row, col):
        return row[col] if col < len(row) else None

    def _parse_month(self, value):
        if isinstance(value, datetime):
            return value.strftime('%m/%Y'), date(value.year, value.month, 1)
        if isinstance(value, date):
            return value.strftime('%m/%Y'), date(value.year, value.month, 1)
        match = self.MONTH_RE.search(str(value or '').strip())
        if not match:
            return False, False
        month, year = int(match.group(1)), int(match.group(2))
        try:
            month_date = date(year, month, 1)
        except ValueError:
            return False, False
        return f'{month:02d}/{year}', month_date

    def _format_month_display(self, value):
        if value in (None, ''):
            return ''
        if isinstance(value, datetime):
            return value.strftime('%d/%m/%Y')
        if isinstance(value, date):
            return value.strftime('%d/%m/%Y')
        return str(value).strip()

    def _parse_float(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(' ', '').replace(',', '.')
        try:
            return float(text)
        except ValueError:
            raise UserError(_('Không đọc được số lượng "%s".') % value)

    def _normalize_ma_nvl(self, value):
        if value in (None, ''):
            return ''
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        if isinstance(value, int):
            return str(value)
        text = str(value).strip()
        if text.endswith('.0') and text[:-2].isdigit():
            return text[:-2]
        return text

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

    def _get_company_codes(self):
        return sorted({
            (c.company_code or '').strip()
            for c in self.env['res.company'].sudo().search([])
            if (c.company_code or '').strip()
        })

    def _apply_company_code_validation(self, wb, ws, company_codes):
        if not company_codes:
            return
        ref_sheet = wb.create_sheet('_company_codes')
        ref_sheet.sheet_state = 'hidden'
        for row_idx, code in enumerate(company_codes, start=1):
            ref_sheet.cell(row=row_idx, column=1, value=code)
        dv = DataValidation(
            type='list',
            formula1=f"='_company_codes'!$A$1:$A${len(company_codes)}",
            allow_blank=False,
        )
        dv.error = _('Chỉ được chọn mã đơn vị có trong danh mục.')
        dv.errorTitle = _('Đơn vị không hợp lệ')
        ws.add_data_validation(dv)
        dv.add('A2:A5000')

    def _apply_vdd_template_style(self, ws, max_col=6):
        body_font = Font(name='Times New Roman', size=10)
        header_font = Font(name='Times New Roman', size=10, bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='3F6F8F')
        header_side = Side(style='thin', color='2F556D')
        header_border = Border(
            left=header_side, right=header_side, top=header_side, bottom=header_side,
        )
        for cell in ws[1][:max_col]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = header_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[1].height = 22
        ws.freeze_panes = 'A2'
        for row in ws.iter_rows(min_row=2, max_row=5001, min_col=1, max_col=max_col):
            for cell in row:
                cell.font = body_font
                cell.alignment = Alignment(vertical='center')

    def _get_import_worksheet(self, workbook):
        if self.TEMPLATE_SHEET_NAME in workbook.sheetnames:
            return workbook[self.TEMPLATE_SHEET_NAME]
        for name in workbook.sheetnames:
            if not name.startswith('_'):
                return workbook[name]
        return workbook.active

    def _read_data_rows(self):
        if not self.file_data:
            raise UserError(_('Vui lòng chọn file Excel.'))
        try:
            data = base64.b64decode(self.file_data)
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='Data Validation extension', category=UserWarning)
                workbook = load_workbook(io.BytesIO(data), data_only=True)
        except Exception as exc:
            raise UserError(_('Không đọc được file Excel: %s') % exc)
        ws = self._get_import_worksheet(workbook)
        return list(ws.iter_rows(min_row=self.DATA_START_ROW, values_only=True))

    def action_download_template(self):
        self.ensure_one()
        wb = Workbook()
        ws = wb.active
        ws.title = self.TEMPLATE_SHEET_NAME
        headers = ['Đơn vị', 'Số PR', 'Mã NVL', 'Tên NVL', 'Tháng', 'Số lượng']
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=1, column=col_idx, value=label)
        self._apply_vdd_template_style(ws)
        self._apply_company_code_validation(wb, ws, self._get_company_codes())
        for col_idx, width in enumerate([14, 24, 26, 36, 14, 16], start=1):
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = width
        return self._xlsx_download_action(wb, 'Template_vat_tu_di_duong.xlsx')

    def action_import(self):
        self.ensure_one()
        rows = self._read_data_rows()
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu (từ dòng 2).'))

        Company = self.env['res.company'].sudo()
        MaHang = self.env['ma.hang'].sudo()
        VatTuDiDuong = self.env['vat.tu.di.duong'].sudo()

        errors = []
        created = updated = 0
        for row_number, row in enumerate(rows, start=self.DATA_START_ROW):
            if not any(cell not in (None, '') for cell in row):
                continue

            company_code = str(self._cell(row, self.COL_COMPANY) or '').strip()
            pr_number = str(self._cell(row, self.COL_PR) or '').strip()
            ma_nvl = self._normalize_ma_nvl(self._cell(row, self.COL_MA_NVL))
            ten_nvl = str(self._cell(row, self.COL_TEN_NVL) or '').strip()
            month_raw = self._cell(row, self.COL_MONTH)
            month_key, month_date = self._parse_month(month_raw)

            row_errors = []
            if not company_code:
                row_errors.append(_('Dòng %d: thiếu Đơn vị.') % row_number)
            if not pr_number:
                row_errors.append(_('Dòng %d: thiếu Số PR.') % row_number)
            if not ma_nvl:
                row_errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)
            if not month_key:
                month_display = self._format_month_display(month_raw)
                if month_display:
                    row_errors.append(
                        _('Dòng %d: Tháng "%s" không đúng định dạng MM/YYYY.') % (row_number, month_display)
                    )
                else:
                    row_errors.append(_('Dòng %d: thiếu Tháng.') % row_number)

            qty_raw = self._cell(row, self.COL_QTY)
            if qty_raw in (None, ''):
                row_errors.append(_('Dòng %d: thiếu Số lượng.') % row_number)
            else:
                try:
                    so_luong = self._parse_float(qty_raw)
                    if so_luong < 0:
                        row_errors.append(_('Dòng %d: Số lượng không được âm.') % row_number)
                except UserError as exc:
                    row_errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))

            company = self.env['res.company']
            if company_code:
                company = Company.search([('company_code', '=', company_code)], limit=1)
                if not company:
                    row_errors.append(_('Dòng %d: Đơn vị "%s" không tồn tại.') % (row_number, company_code))

            master = self.env['ma.hang']
            if ma_nvl:
                master = MaHang.search([('ma_sap', '=', ma_nvl)], limit=1)
                if not master:
                    row_errors.append(
                        _('Dòng %d: Mã NVL "%s" không có trong danh mục mã hàng.') % (row_number, ma_nvl)
                    )

            if row_errors:
                errors.extend(row_errors)
                continue

            vals = {
                'nguon': self.nguon,
                'company_id': company.id,
                'pr_number': pr_number,
                'ma_nvl': ma_nvl,
                'ten_nvl': ten_nvl or master.ten_hang or False,
                'month_key': month_key,
                'month_date': month_date,
                'so_luong': so_luong,
            }
            existing = VatTuDiDuong.search([
                ('nguon', '=', self.nguon),
                ('company_id', '=', company.id),
                ('pr_number', '=', pr_number),
                ('ma_nvl', '=', ma_nvl),
                ('month_key', '=', month_key),
            ], limit=1)
            if existing:
                existing.write(vals)
                updated += 1
            else:
                VatTuDiDuong.create(vals)
                created += 1

        if errors:
            shown = errors[:80]
            message = '\n'.join('- %s' % err for err in shown)
            if len(errors) > 80:
                message += _('\n... còn %d lỗi khác.') % (len(errors) - 80)
            raise UserError(message)

        parts = []
        if created:
            parts.append(_('thêm %d dòng mới') % created)
        if updated:
            parts.append(_('cập nhật %d dòng') % updated)
        if parts:
            message = _('Import thành công: %s.') % ', '.join(parts)
        else:
            message = _('Không có dữ liệu hợp lệ để import.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import vật tư đi đường'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
