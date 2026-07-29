# -*- coding: utf-8 -*-
from openpyxl import Workbook

from odoo import _, fields, models
from odoo.exceptions import UserError

TEMPLATE_HEADERS = ['Đơn vị', 'Mã NVL', 'Tên NVL (chỉ để tham khảo)', 'Phần trăm']
TEMPLATE_WIDTHS = [14, 26, 36, 14]
# Số mã liệt kê tối đa trong thông báo kết quả, tránh message dài vô hạn.
NOTIFY_ITEM_LIMIT = 10


class ImportMaHangPhanTramWizard(models.TransientModel):
    _name = 'import.ma.hang.phan.tram.wizard'
    _description = 'Import phần trăm mã hàng'
    _inherit = ['vat.tu.excel.mixin']

    TEMPLATE_SHEET_NAME = 'Phan tram ma hang'
    DATA_START_ROW = 2
    # Cột C (Tên NVL) chỉ để người nhập dễ đối chiếu, không được đọc khi import.
    COL_COMPANY, COL_MA_NVL, COL_TEN_NVL, COL_PHAN_TRAM = range(4)

    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')

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
        return self._xlsx_download_action(wb, 'Template_phan_tram_ma_hang.xlsx')

    def _parse_rows(self, rows, company_by_code):
        errors = []
        parsed = []
        seen_keys = set()

        for row_number, row in enumerate(rows, start=self.DATA_START_ROW):
            if not any(cell not in (None, '') for cell in row):
                continue

            company_code = str(self._cell(row, self.COL_COMPANY) or '').strip()
            ma_nvl = self._normalize_ma_nvl(self._cell(row, self.COL_MA_NVL))

            row_errors = []
            if not company_code:
                row_errors.append(_('Dòng %d: thiếu Đơn vị.') % row_number)
            if not ma_nvl:
                row_errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)

            company = company_by_code.get(company_code) if company_code else False
            if company_code and not company:
                row_errors.append(
                    _('Dòng %d: Đơn vị "%s" không tồn tại.') % (row_number, company_code))

            phan_tram = 0.0
            try:
                phan_tram = self._parse_number(
                    self._cell(row, self.COL_PHAN_TRAM), label=_('phần trăm'))
                if phan_tram < 0:
                    row_errors.append(_('Dòng %d: Phần trăm không được âm.') % row_number)
            except UserError as exc:
                row_errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))

            if company and ma_nvl:
                dup_key = (company.id, ma_nvl)
                if dup_key in seen_keys:
                    row_errors.append(
                        _('Dòng %d: trùng Đơn vị + Mã NVL trong file.') % row_number)
                else:
                    seen_keys.add(dup_key)

            if row_errors:
                errors.extend(row_errors)
                continue

            parsed.append({
                'row_number': row_number,
                'company': company,
                'company_code': company_code,
                'ma_nvl': ma_nvl,
                'phan_tram': phan_tram,
            })

        return parsed, errors

    def _check_codes_in_catalog(self, parsed, errors):
        """Kiểm tra mã tồn tại trong danh mục mã hàng bằng 1 query cho cả file."""
        if not parsed:
            return
        catalog = {
            (rec.company_id.id, rec.ma_sap)
            for rec in self.env['ma.hang'].sudo().search([
                ('company_id', 'in', list({item['company'].id for item in parsed})),
                ('ma_sap', 'in', list({item['ma_nvl'] for item in parsed})),
            ])
        }
        for item in parsed:
            if (item['company'].id, item['ma_nvl']) not in catalog:
                errors.append(_(
                    'Dòng %d: Mã NVL "%s" không có trong danh mục mã hàng (ĐVCS %s).'
                ) % (item['row_number'], item['ma_nvl'], item['company_code']))

    def _apply_rows(self, parsed):
        PhanTram = self.env['ma.hang.phan.tram'].sudo()
        existing_map = {
            (rec.company_id.id, rec.ma_sap): rec
            for rec in PhanTram.search([
                ('company_id', 'in', list({item['company'].id for item in parsed})),
                ('ma_sap', 'in', list({item['ma_nvl'] for item in parsed})),
            ])
        }

        to_create = []
        ids_by_value = {}
        created_items, updated_items = [], []
        for item in parsed:
            label = '%s (%s, %s%%)' % (item['ma_nvl'], item['company_code'], item['phan_tram'])
            existing = existing_map.get((item['company'].id, item['ma_nvl']))
            if existing:
                ids_by_value.setdefault(item['phan_tram'], []).append(existing.id)
                updated_items.append(label)
            else:
                to_create.append({
                    'company_id': item['company'].id,
                    'ma_sap': item['ma_nvl'],
                    'phan_tram': item['phan_tram'],
                })
                created_items.append(label)

        # Gom theo giá trị phần trăm: chỉ vài query thay vì mỗi dòng một write.
        for value, ids in ids_by_value.items():
            PhanTram.browse(ids).write({'phan_tram': value})
        if to_create:
            PhanTram.create(to_create)

        return created_items, updated_items

    def _summarize_items(self, items):
        shown = ', '.join(items[:NOTIFY_ITEM_LIMIT])
        if len(items) > NOTIFY_ITEM_LIMIT:
            shown += _(' và %d mã khác') % (len(items) - NOTIFY_ITEM_LIMIT)
        return shown

    def action_import(self):
        self.ensure_one()
        rows = self._read_data_rows()
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu (từ dòng 2).'))

        parsed, errors = self._parse_rows(rows, self._company_by_code())
        self._check_codes_in_catalog(parsed, errors)
        self._raise_import_errors(errors)

        created_items, updated_items = self._apply_rows(parsed) if parsed else ([], [])

        parts = []
        if created_items:
            parts.append(_('thêm %s') % self._summarize_items(created_items))
        if updated_items:
            parts.append(_('cập nhật %s') % self._summarize_items(updated_items))
        message = (
            _('Import thành công: %s.') % ', '.join(parts) if parts
            else _('Không có dữ liệu hợp lệ để import.')
        )

        return self._notify_and_close(
            _('Import phần trăm mã hàng'), message, success=bool(parts))
