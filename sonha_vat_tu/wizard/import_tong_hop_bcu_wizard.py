# -*- coding: utf-8 -*-
import base64
import io
import warnings

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from odoo import _, fields, models
from odoo.exceptions import UserError


class ImportTongHopBcuWizard(models.TransientModel):
    """Import hàng đi đường BCU — chỉ ghi 4 cột ve_du_kien_t0..t3 để đối chiếu.

    Không gọi fn_tong_hop_vat_tu, không tính lại ton_cuoi_* / so_luong_thieu.
    Muốn BCU ảnh hưởng số tính toán → chạy lại Tổng hợp B4 (fn_tong_hop_vat_tu).
    """
    _name = 'import.tong.hop.bcu.wizard'
    _description = 'Import hàng đi đường BCU (Tổng hợp vật tư cần sản xuất)'

    TEMPLATE_SHEET_NAME = 'Hang di duong BCU'
    META_ROW = 1
    HEADER_ROW = 4
    DATA_START_ROW = 5
    META_FONT_SIZE = 13
    COL_MA_NVL, COL_TEN_NVL = 0, 1
    COL_T0, COL_T1, COL_T2, COL_T3 = 2, 3, 4, 5

    period_id = fields.Many2one(
        'ke.hoach.vat.tu',
        string='Kỳ kế hoạch',
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('default_period_id') or self.env.context.get('active_id'),
    )
    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')

    def _cell(self, row, col):
        return row[col] if col < len(row) else None

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

    def _parse_float(self, value, default=0.0):
        if value in (None, ''):
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(' ', '').replace(',', '.')
        try:
            return float(text)
        except ValueError:
            raise UserError(_('Không đọc được số lượng "%s".') % value)

    def _get_month_headers(self):
        self.ensure_one()
        return [
            _('Tháng %s') % month
            for month in self.period_id._get_horizon_months()
        ]

    def _get_b4_lines(self):
        self.ensure_one()
        return self.env['tong.hop.vat.tu'].sudo().search([
            ('period_id', '=', self.period_id.id),
            ('don_vi_kd_id', '=', False),
        ], order='ma_sap, id')

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

    def _apply_template_style(self, ws, max_col):
        body_font = Font(name='Times New Roman', size=10)
        meta_label_font = Font(name='Times New Roman', size=self.META_FONT_SIZE, bold=True)
        meta_value_font = Font(name='Times New Roman', size=self.META_FONT_SIZE, bold=True)
        header_font = Font(name='Times New Roman', size=10, bold=True, color='FFFFFF')
        header_fill = PatternFill(fill_type='solid', fgColor='3F6F8F')
        header_side = Side(style='thin', color='2F556D')
        header_border = Border(
            left=header_side, right=header_side, top=header_side, bottom=header_side,
        )
        ws.cell(row=self.META_ROW, column=1).font = meta_label_font
        ws.cell(row=self.META_ROW, column=2).font = meta_value_font
        ws.row_dimensions[self.META_ROW].height = 24
        for cell in ws[self.HEADER_ROW][:max_col]:
            cell.font = header_font
            cell.fill = header_fill
            cell.border = header_border
            cell.alignment = Alignment(horizontal='center', vertical='center')
        ws.row_dimensions[self.HEADER_ROW].height = 22
        ws.freeze_panes = 'A%d' % self.DATA_START_ROW
        for row in ws.iter_rows(
            min_row=self.DATA_START_ROW, max_row=5001, min_col=1, max_col=max_col,
        ):
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

    def _read_import_worksheet(self):
        if not self.file_data:
            raise UserError(_('Vui lòng chọn file Excel.'))
        try:
            data = base64.b64decode(self.file_data)
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='Data Validation extension', category=UserWarning)
                workbook = load_workbook(io.BytesIO(data), data_only=True)
        except Exception as exc:
            raise UserError(_('Không đọc được file Excel: %s') % exc)
        return self._get_import_worksheet(workbook)

    def _parse_doc_code_from_sheet(self, ws):
        label = str(ws.cell(row=self.META_ROW, column=1).value or '').strip()
        value = str(ws.cell(row=self.META_ROW, column=2).value or '').strip()
        if label == _('Số chứng từ') and value == _('Mã NVL'):
            return 'legacy_column'
        if label == _('Số chứng từ') and value:
            return value
        return False

    def _resolve_data_start_row(self, ws, legacy_column):
        if legacy_column:
            return 2
        for header_row in (self.HEADER_ROW, 2):
            header_a = str(ws.cell(row=header_row, column=1).value or '').strip()
            if header_a == _('Mã NVL'):
                return header_row + 1
        return self.DATA_START_ROW

    def action_download_template(self):
        self.ensure_one()
        if not self.period_id.code:
            raise UserError(_('Kỳ kế hoạch chưa có số chứng từ.'))

        month_headers = self._get_month_headers()
        if len(month_headers) != 4:
            raise UserError(_('Kỳ kế hoạch chưa xác định được 4 tháng tính toán.'))

        wb = Workbook()
        ws = wb.active
        ws.title = self.TEMPLATE_SHEET_NAME
        ws.cell(row=self.META_ROW, column=1, value=_('Số chứng từ'))
        ws.cell(row=self.META_ROW, column=2, value=self.period_id.code)

        headers = [_('Mã NVL'), _('Tên NVL')] + month_headers
        for col_idx, label in enumerate(headers, start=1):
            ws.cell(row=self.HEADER_ROW, column=col_idx, value=label)

        row_idx = self.DATA_START_ROW
        for line in self._get_b4_lines():
            ws.cell(row=row_idx, column=1, value=line.ma_sap or '')
            ws.cell(row=row_idx, column=2, value=line.ten_nvl or '')
            ws.cell(row=row_idx, column=3, value=line.ve_du_kien_t0 or 0)
            ws.cell(row=row_idx, column=4, value=line.ve_du_kien_t1 or 0)
            ws.cell(row=row_idx, column=5, value=line.ve_du_kien_t2 or 0)
            ws.cell(row=row_idx, column=6, value=line.ve_du_kien_t3 or 0)
            row_idx += 1

        max_col = len(headers)
        self._apply_template_style(ws, max_col)
        widths = [16, 36, 16, 16, 16, 16]
        for col_idx, width in enumerate(widths[:max_col], start=1):
            ws.column_dimensions[ws.cell(row=self.HEADER_ROW, column=col_idx).column_letter].width = width

        filename = 'Template_hang_di_duong_BCU_%s.xlsx' % (self.period_id.code or 'ky')
        return self._xlsx_download_action(wb, filename)

    def action_import(self):
        self.ensure_one()
        if not self.period_id.code:
            raise UserError(_('Kỳ kế hoạch chưa có số chứng từ.'))

        ws = self._read_import_worksheet()
        expected_code = (self.period_id.code or '').strip()
        doc_code = self._parse_doc_code_from_sheet(ws)
        legacy_column = doc_code == 'legacy_column'
        if legacy_column:
            doc_code = False
        elif not doc_code:
            raise UserError(_('File Excel thiếu Số chứng từ ở ô B1.'))
        elif doc_code != expected_code:
            raise UserError(
                _('Số chứng từ "%s" không khớp kỳ "%s".') % (doc_code, expected_code)
            )

        data_start = self._resolve_data_start_row(ws, legacy_column)
        rows = list(ws.iter_rows(min_row=data_start, values_only=True))
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu.'))

        errors = []
        updates = []

        col_ma = 1 if legacy_column else self.COL_MA_NVL
        col_t0 = 4 if legacy_column else self.COL_T0
        col_t1 = 5 if legacy_column else self.COL_T1
        col_t2 = 6 if legacy_column else self.COL_T2
        col_t3 = 7 if legacy_column else self.COL_T3

        existing_map = {
            line.ma_sap: line.id
            for line in self._get_b4_lines()
        }

        for row_number, row in enumerate(rows, start=data_start):
            if not any(cell not in (None, '') for cell in row):
                continue

            if legacy_column:
                row_doc = str(self._cell(row, 0) or '').strip()
                if not row_doc:
                    errors.append(_('Dòng %d: thiếu Số chứng từ.') % row_number)
                    continue
                if row_doc != expected_code:
                    errors.append(
                        _('Dòng %d: Số chứng từ "%s" không khớp kỳ "%s".')
                        % (row_number, row_doc, expected_code)
                    )
                    continue

            ma_nvl = self._normalize_ma_nvl(self._cell(row, col_ma))

            row_errors = []
            if not ma_nvl:
                row_errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)

            line_id = existing_map.get(ma_nvl) if ma_nvl else False
            if ma_nvl and not row_errors and not line_id:
                row_errors.append(
                    _('Dòng %d: Mã NVL "%s" không có trong Tổng hợp vật tư cần sản xuất của kỳ này.')
                    % (row_number, ma_nvl)
                )

            if row_errors:
                errors.extend(row_errors)
                continue

            try:
                vals = {
                    've_du_kien_t0': self._parse_float(self._cell(row, col_t0)),
                    've_du_kien_t1': self._parse_float(self._cell(row, col_t1)),
                    've_du_kien_t2': self._parse_float(self._cell(row, col_t2)),
                    've_du_kien_t3': self._parse_float(self._cell(row, col_t3)),
                }
            except UserError as exc:
                errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))
                continue

            if any(vals[f've_du_kien_t{i}'] < 0 for i in range(4)):
                errors.append(_('Dòng %d: Số lượng không được âm.') % row_number)
                continue

            updates.append((
                line_id,
                vals['ve_du_kien_t0'],
                vals['ve_du_kien_t1'],
                vals['ve_du_kien_t2'],
                vals['ve_du_kien_t3'],
            ))

        if errors:
            shown = errors[:80]
            message = '\n'.join('- %s' % err for err in shown)
            if len(errors) > 80:
                message += _('\n... còn %d lỗi khác.') % (len(errors) - 80)
            raise UserError(message)

        updated = len(updates)
        if updated:
            self.env.cr.execute(
                """
                UPDATE tong_hop_vat_tu th
                   SET ve_du_kien_t0 = v.t0,
                       ve_du_kien_t1 = v.t1,
                       ve_du_kien_t2 = v.t2,
                       ve_du_kien_t3 = v.t3,
                       write_uid = %s,
                       write_date = NOW()
                  FROM unnest(%s::int[], %s::numeric[], %s::numeric[],
                              %s::numeric[], %s::numeric[])
                       AS v(id, t0, t1, t2, t3)
                 WHERE th.id = v.id
                """,
                (
                    self.env.uid,
                    [u[0] for u in updates],
                    [u[1] for u in updates],
                    [u[2] for u in updates],
                    [u[3] for u in updates],
                    [u[4] for u in updates],
                ),
            )
            self.env['tong.hop.vat.tu'].browse([u[0] for u in updates]).invalidate_recordset([
                've_du_kien_t0', 've_du_kien_t1', 've_du_kien_t2', 've_du_kien_t3',
                'write_date', 'write_uid',
            ])
            message = _(
                'Import thành công: cập nhật %d dòng hàng đi đường BCU '
                '(chỉ cột đối chiếu, không tính lại tồn cuối/thiếu).'
            ) % updated
        else:
            message = _('Không có dữ liệu hợp lệ để import.')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import hàng đi đường BCU'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }
