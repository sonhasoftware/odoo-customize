# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

_QTY_FIELD_BY_OFFSET = {
    0: 'tong_sl_vt_can_dung_t0',
    1: 'tong_sl_vt_can_dung_t1',
    2: 'tong_sl_vt_can_dung_t2',
    3: 'tong_sl_vt_can_dung_t3',
}


class ImportKhDatVatTuWizard(models.TransientModel):
    _name = 'import.kh.dat.vat.tu.wizard'
    _description = 'Import cần dùng kế hoạch đặt vật tư (B5)'
    _inherit = ['vat.tu.excel.mixin']

    TEMPLATE_SHEET_NAME = 'Ke hoach dat vat tu'
    META_ROW_CODE = 1
    META_ROW_MONTH = 2
    META_ROW_COMPANY = 3
    HEADER_ROW1 = 4
    HEADER_ROW2 = 5
    DATA_START_ROW = 6

    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')
    period_id = fields.Many2one(
        'ke.hoach.vat.tu',
        string='Kỳ kế hoạch',
        readonly=True,
        default=lambda self: self.env.context.get('default_period_id'),
    )

    def _validate_period_state(self):
        self.ensure_one()
        period = self.period_id
        if not period:
            raise UserError(_('Thiếu kỳ kế hoạch.'))
        if period.state != 'dat_hang':
            raise UserError(_('Chỉ import được ở bước Kế hoạch đặt vật tư.'))
        if not period.kh_dat_vat_tu_ids:
            raise UserError(_('Chưa có dữ liệu kế hoạch đặt vật tư trên kỳ này.'))
        return period

    @staticmethod
    def _meta_label(ws, row, col=1):
        return str(ws.cell(row, col).value or '').strip()

    @staticmethod
    def _meta_value(ws, row, col=2):
        return str(ws.cell(row, col).value or '').strip()

    def _validate_meta(self, ws, period):
        label_code = self._meta_label(ws, self.META_ROW_CODE)
        val_code = self._meta_value(ws, self.META_ROW_CODE)
        if label_code != _('Số chứng từ') or not val_code:
            raise UserError(_('File Excel thiếu hoặc sai ô Số chứng từ (A1:B1).'))
        expected_code = (period.code or '').strip()
        if val_code != expected_code:
            raise UserError(
                _('Số chứng từ "%(file)s" không khớp kỳ "%(period)s".')
                % {'file': val_code, 'period': expected_code}
            )

        label_month = self._meta_label(ws, self.META_ROW_MONTH)
        val_month = self._meta_value(ws, self.META_ROW_MONTH)
        if label_month != _('Tháng bắt đầu') or not val_month:
            raise UserError(_('File Excel thiếu hoặc sai ô Tháng bắt đầu (A2:B2).'))
        expected_month = (period.period_month or '').strip()
        if val_month != expected_month:
            raise UserError(
                _('Tháng bắt đầu "%(file)s" không khớp kỳ "%(period)s".')
                % {'file': val_month, 'period': expected_month}
            )

        label_company = self._meta_label(ws, self.META_ROW_COMPANY)
        val_company = self._meta_value(ws, self.META_ROW_COMPANY)
        if label_company != _('Đơn vị sản xuất') or not val_company:
            raise UserError(
                _('File Excel thiếu hoặc sai ô Đơn vị sản xuất (A3:B3). '
                  'Vui lòng xuất lại file từ kỳ này.')
            )
        sx = period.company_sx_id
        if not sx:
            raise UserError(_('Kỳ kế hoạch chưa có đơn vị sản xuất.'))
        allowed = {
            (period._get_company_code(sx) or '').strip().upper(),
            (sx.name or '').strip().upper(),
        }
        if val_company.strip().upper() not in allowed:
            raise UserError(
                _('Đơn vị sản xuất "%(file)s" không khớp kỳ "%(period)s".')
                % {
                    'file': val_company,
                    'period': period._get_company_code(sx) or sx.name,
                }
            )

    def _header_group_at_col(self, ws, col):
        """Nhóm cột hàng 4 (Cần dùng / Đi đường…) — xử lý ô merge."""
        for c in range(col, 0, -1):
            val = ws.cell(self.HEADER_ROW1, c).value
            if val not in (None, ''):
                return str(val).strip()
        return ''

    def _find_ma_col_and_can_dung_cols(self, ws, period):
        ma_col = None
        for c in range(1, ws.max_column + 1):
            label4 = str(ws.cell(self.HEADER_ROW1, c).value or '').strip()
            label5 = str(ws.cell(self.HEADER_ROW2, c).value or '').strip()
            if label4 == _('Mã NVL') or label5 == _('Mã NVL'):
                ma_col = c
                break
        if not ma_col:
            raise UserError(_('Không tìm thấy cột "Mã NVL" trên file export B5.'))

        month_parser = self.env['import.vat.tu.di.duong.wizard']
        expected_months = period._get_horizon_months()
        if len(expected_months) < 4:
            raise UserError(_('Kỳ kế hoạch chưa xác định được 4 tháng tính toán.'))

        can_dung_cols = []
        for c in range(1, ws.max_column + 1):
            if self._header_group_at_col(ws, c) != _('Cần dùng'):
                continue
            header = ws.cell(self.HEADER_ROW2, c).value
            month_key = month_parser._month_key_from_header(header)
            if month_key:
                can_dung_cols.append((c, month_key))

        if len(can_dung_cols) < 4:
            raise UserError(
                _('Không tìm đủ 4 cột "Cần dùng" theo tháng trên file Excel.')
            )

        can_dung_cols.sort(key=lambda item: item[0])
        can_dung_cols = can_dung_cols[:4]
        file_months = [mk for _col, mk in can_dung_cols]
        if file_months != expected_months:
            raise UserError(
                _('Tháng trên cột Cần dùng (%s) không khớp kỳ (%s).')
                % (', '.join(file_months), ', '.join(expected_months))
            )
        return ma_col, [col for col, _mk in can_dung_cols]

    def _parse_rows(self, ws, period, ma_col, qty_cols):
        month_labels = period._get_horizon_months()[:4]
        line_map = {
            (line.ma_sap or '').strip(): line
            for line in period.kh_dat_vat_tu_ids
            if (line.ma_sap or '').strip()
        }
        errors = []
        updates = {}
        seen_ma = set()

        for row_number in range(self.DATA_START_ROW, ws.max_row + 1):
            row_vals = [
                ws.cell(row_number, c).value
                for c in range(1, ws.max_column + 1)
            ]
            if not any(v not in (None, '') for v in row_vals):
                continue

            ma_sap = self._normalize_ma_nvl(ws.cell(row_number, ma_col).value)
            if not ma_sap:
                errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)
                continue

            if ma_sap in seen_ma:
                errors.append(
                    _('Dòng %d: Mã NVL "%s" bị trùng trong file.') % (row_number, ma_sap)
                )
                continue
            seen_ma.add(ma_sap)

            if ma_sap not in line_map:
                errors.append(
                    _('Dòng %d: Mã NVL "%s" không tồn tại trên kế hoạch đặt vật tư của kỳ này.')
                    % (row_number, ma_sap)
                )
                continue

            write_vals = {}
            row_errors = False
            for offset, col_idx in enumerate(qty_cols):
                field_name = _QTY_FIELD_BY_OFFSET[offset]
                month_label = month_labels[offset] if offset < len(month_labels) else str(offset)
                label = _('Cần dùng tháng %s') % month_label
                try:
                    qty = self._parse_number(
                        ws.cell(row_number, col_idx).value,
                        default=0.0,
                        label=label,
                    )
                except UserError as exc:
                    errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))
                    row_errors = True
                    break
                if qty < 0:
                    errors.append(
                        _('Dòng %d: %s không được âm.') % (row_number, label)
                    )
                    row_errors = True
                    break
                write_vals[field_name] = qty

            if not row_errors:
                updates[ma_sap] = write_vals

        return updates, errors

    def action_import(self):
        self.ensure_one()
        period = self._validate_period_state()
        wb = self._load_workbook()
        ws = self._get_import_worksheet(wb)
        self._validate_meta(ws, period)
        ma_col, qty_cols = self._find_ma_col_and_can_dung_cols(ws, period)
        updates, errors = self._parse_rows(ws, period, ma_col, qty_cols)
        self._raise_import_errors(
            errors,
            header=_('Import có lỗi, chưa cập nhật dữ liệu:'),
        )
        if not updates:
            raise UserError(_('Không có dòng dữ liệu hợp lệ để import.'))

        line_map = {
            (line.ma_sap or '').strip(): line
            for line in period.kh_dat_vat_tu_ids
        }
        for ma_sap, vals in updates.items():
            line_map[ma_sap].with_context(is_importing=True).write(vals)

        self._post_period_import_file_log(
            period,
            '<p><b>Đã import file kế hoạch đặt vật tư %s.</b></p>'
            % (self.file_name or '-'),
        )

        return self._notify_and_close(
            _('Import thành công file kế hoạch đặt vật tư'),
            '',
            success=True,
        )
