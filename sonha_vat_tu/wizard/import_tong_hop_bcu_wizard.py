# -*- coding: utf-8 -*-
from openpyxl import Workbook
from openpyxl.styles import Font

from odoo import _, fields, models
from odoo.exceptions import UserError

TEMPLATE_WIDTHS = [16, 36, 16, 16, 16, 16]


class ImportTongHopBcuWizard(models.TransientModel):
    """Import hàng đi đường BCU — chỉ ghi 4 cột ve_du_kien_t0..t3 để đối chiếu.

    Không gọi fn_tong_hop_vat_tu, không tính lại ton_cuoi_* / so_luong_thieu.
    Muốn BCU ảnh hưởng số tính toán → chạy lại Tổng hợp B4 (fn_tong_hop_vat_tu).
    """
    _name = 'import.tong.hop.bcu.wizard'
    _description = 'Import hàng đi đường BCU (Tổng hợp vật tư cần sản xuất)'
    _inherit = ['vat.tu.excel.mixin']

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
            for offset in range(4):
                ws.cell(
                    row=row_idx, column=3 + offset,
                    value=line['ve_du_kien_t%d' % offset] or 0,
                )
            row_idx += 1

        max_col = len(headers)
        meta_font = Font(name='Times New Roman', size=self.META_FONT_SIZE, bold=True)
        ws.cell(row=self.META_ROW, column=1).font = meta_font
        ws.cell(row=self.META_ROW, column=2).font = meta_font
        ws.row_dimensions[self.META_ROW].height = 24
        self._style_excel_header(ws, max_col, header_row=self.HEADER_ROW)
        self._style_excel_body(ws, max_col, self.DATA_START_ROW, row_idx - 1)
        self._set_excel_widths(ws, TEMPLATE_WIDTHS[:max_col])

        return self._xlsx_download_action(
            wb, 'Template_hang_di_duong_BCU_%s.xlsx' % (self.period_id.code or 'ky'))

    def action_import(self):
        self.ensure_one()
        if not self.period_id.code:
            raise UserError(_('Kỳ kế hoạch chưa có số chứng từ.'))

        ws = self._get_import_worksheet()
        expected_code = (self.period_id.code or '').strip()
        doc_code = self._parse_doc_code_from_sheet(ws)
        legacy_column = doc_code == 'legacy_column'
        if legacy_column:
            doc_code = False
        elif not doc_code:
            raise UserError(_('File Excel thiếu Số chứng từ ở ô B1.'))
        elif doc_code != expected_code:
            raise UserError(
                _('Số chứng từ "%s" không khớp kỳ "%s".') % (doc_code, expected_code))

        data_start = self._resolve_data_start_row(ws, legacy_column)
        rows = list(ws.iter_rows(min_row=data_start, values_only=True))
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu.'))

        errors = []
        updates = []
        col_ma = 1 if legacy_column else self.COL_MA_NVL
        month_cols = (
            (4, 5, 6, 7) if legacy_column
            else (self.COL_T0, self.COL_T1, self.COL_T2, self.COL_T3)
        )
        existing_map = {line.ma_sap: line.id for line in self._get_b4_lines()}

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
            if not ma_nvl:
                errors.append(_('Dòng %d: thiếu Mã NVL.') % row_number)
                continue

            line_id = existing_map.get(ma_nvl)
            if not line_id:
                errors.append(
                    _('Dòng %d: Mã NVL "%s" không có trong Tổng hợp vật tư cần sản xuất của kỳ này.')
                    % (row_number, ma_nvl)
                )
                continue

            try:
                qtys = [
                    self._parse_number(self._cell(row, col), default=0.0)
                    for col in month_cols
                ]
            except UserError as exc:
                errors.append(_('Dòng %d: %s') % (row_number, exc.args[0]))
                continue

            if any(qty < 0 for qty in qtys):
                errors.append(_('Dòng %d: Số lượng không được âm.') % row_number)
                continue

            updates.append([line_id] + qtys)

        self._raise_import_errors(errors)

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
                       write_date = NOW() AT TIME ZONE 'UTC'
                  FROM unnest(%s::int[], %s::numeric[], %s::numeric[],
                              %s::numeric[], %s::numeric[])
                       AS v(id, t0, t1, t2, t3)
                 WHERE th.id = v.id
                """,
                [self.env.uid] + [[u[idx] for u in updates] for idx in range(5)],
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

        return self._notify_and_close(
            _('Import hàng đi đường BCU'), message, success=bool(updated))
