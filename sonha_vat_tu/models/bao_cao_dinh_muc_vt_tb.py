# -*- coding: utf-8 -*-
import base64
import io
import json

from openpyxl import Workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

from odoo import _, api, fields, models
from odoo.exceptions import UserError

REPORT_MONTH_COUNT = 3
QTY_FIELDS = tuple('qty_t%d' % idx for idx in range(REPORT_MONTH_COUNT))

DMTB_NHOM_SELECTION = [
    ('innox', 'Innox'),
    ('nhua', 'Nhựa'),
]

DMTB_MA_LINH_VUC = {
    'innox': 'IOXC',
    'nhua': 'NHUA',
}

DMTB_SL_LABEL = {
    'innox': 'SL Innox',
    'nhua': 'SL Nhựa',
}


class BaoCaoDinhMucVtTbWizard(models.TransientModel):
    _name = 'bao.cao.dinh.muc.vt.tb.wizard'
    _description = 'Wizard báo cáo định mức vật tư trung bình'

    period_ids = fields.Many2many(
        'ke.hoach.vat.tu',
        'bao_cao_dmtb_wizard_period_rel',
        'wizard_id',
        'period_id',
        string='Kế hoạch',
        help='Chọn nhiều kỳ — mỗi kỳ tương ứng một đơn vị sản xuất (một dòng báo cáo).',
    )
    nhom_linh_vuc = fields.Selection(
        DMTB_NHOM_SELECTION,
        string='Nhóm',
        required=True,
        default='innox',
        help='Lọc NVL theo ma_linh_vuc trên v_mdm_hang_hoa_bcu (Innox=IOXC, Nhựa=NHUA).',
    )
    nguon_sl_sp = fields.Selection(
        [
            ('khkd', 'Kế hoạch kinh doanh'),
            ('khsx', 'Kế hoạch sản xuất'),
        ],
        string='Nguồn',
        required=True,
        default='khkd',
    )
    sl_qty_column_label = fields.Char(string='Nhãn cột SL', readonly=True)
    period_codes = fields.Char(string='Mã các kỳ', readonly=True)
    period_month = fields.Char(string='Tháng kế hoạch', readonly=True)
    column_spec_json = fields.Text(string='Cột tháng (JSON)', readonly=True)
    line_ids = fields.One2many(
        'bao.cao.dinh.muc.vt.tb.line', 'wizard_id', string='Chi tiết')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        period_id = self.env.context.get('default_period_id')
        if not period_id:
            active_id = self.env.context.get('active_id')
            active_model = self.env.context.get('active_model')
            if active_model == 'ke.hoach.vat.tu' and active_id:
                period_id = active_id
        if period_id and 'period_ids' in fields_list:
            res['period_ids'] = [(6, 0, [period_id])]
        return res

    def _plan_model_name(self):
        self.ensure_one()
        return (
            'ke.hoach.kinh.doanh' if self.nguon_sl_sp == 'khkd'
            else 'ke.hoach.san.xuat'
        )

    def _ma_linh_vuc_code(self):
        self.ensure_one()
        code = DMTB_MA_LINH_VUC.get(self.nhom_linh_vuc)
        if not code:
            raise UserError(_('Vui lòng chọn nhóm Innox hoặc Nhựa.'))
        return code

    def _nhom_label(self):
        self.ensure_one()
        return dict(DMTB_NHOM_SELECTION).get(self.nhom_linh_vuc, self.nhom_linh_vuc)

    def _selected_periods(self):
        self.ensure_one()
        if not self.period_ids:
            raise UserError(_('Vui lòng chọn ít nhất một kỳ kế hoạch.'))
        periods = self.period_ids.sorted(
            key=lambda p: (
                (p.company_sx_id.company_code or p.company_sx_id.name or '').upper(),
                p.period_month or '',
                p.code or '',
            )
        )
        months = {(p.period_month or '').strip() for p in periods if p.period_month}
        if len(months) > 1:
            raise UserError(_(
                'Các kỳ đã chọn phải cùng tháng kế hoạch (hiện có: %(months)s).',
                months=', '.join(sorted(months)),
            ))
        return periods

    @staticmethod
    def _report_month_keys(period):
        horizon = period._get_horizon_months()
        if len(horizon) < REPORT_MONTH_COUNT:
            raise UserError(_(
                'Kỳ "%(code)s" không xác định được %(count)s tháng báo cáo.',
                code=period.code or period.display_name,
                count=REPORT_MONTH_COUNT,
            ))
        return horizon[:REPORT_MONTH_COUNT]

    def _filter_nvl_lines(self, nvl_lines, linh_vuc_code):
        nvl_codes = {
            (line.ma_nvl or '').strip() for line in nvl_lines if line.ma_nvl
        }
        linh_vuc_map = self.env['ma.hang'].get_ma_linh_vuc_map(nvl_codes)
        return nvl_lines.filtered(
            lambda line: linh_vuc_map.get((line.ma_nvl or '').strip()) == linh_vuc_code
        )

    def _aggregate_period(self, period, linh_vuc_code):
        all_nvl_lines = self.env['dinh.muc'].search([
            ('period_id', '=', period.id),
        ])
        nvl_lines = self._filter_nvl_lines(all_nvl_lines, linh_vuc_code)
        sap_codes = {
            (line.ma_sap or '').strip() for line in nvl_lines if line.ma_sap
        }
        plan_model = self._plan_model_name()
        if sap_codes:
            plan_lines = self.env[plan_model].search([
                ('period_id', '=', period.id),
                ('ma_sap', 'in', list(sap_codes)),
            ])
        else:
            plan_lines = self.env[plan_model].browse()

        month_keys = self._report_month_keys(period)
        row_metrics = []
        for idx in range(REPORT_MONTH_COUNT):
            sp = sum(
                getattr(line, QTY_FIELDS[idx]) or 0.0 for line in plan_lines
            )
            nvl = sum(
                getattr(line, QTY_FIELDS[idx]) or 0.0 for line in nvl_lines
            )
            row_metrics.append({'sl_sp': sp, 'sl_nvl': nvl})

        return month_keys, row_metrics, plan_lines, nvl_lines

    def _load_ghi_chu_map(self, periods, nhom_linh_vuc):
        GhiChu = self.env['dmtb.ghi.chu'].sudo()
        rows = GhiChu.search([
            ('period_id', 'in', periods.ids),
            ('nhom_linh_vuc', '=', nhom_linh_vuc),
            ('nguon_sl_sp', '=', self.nguon_sl_sp),
        ])
        return {
            (rec.period_id.id, rec.company_sx_id.id): (rec.noi_dung or '')
            for rec in rows
        }

    def _populate_lines(self):
        self.ensure_one()
        periods = self._selected_periods()
        nhom = self.nhom_linh_vuc
        linh_vuc_code = self._ma_linh_vuc_code()
        nhom_label = self._nhom_label()
        ghi_chu_map = self._load_ghi_chu_map(periods, nhom)

        column_keys = self._report_month_keys(periods[0])
        column_spec = [{'month_key': mk, 'label': mk} for mk in column_keys]
        self.column_spec_json = json.dumps(column_spec, ensure_ascii=False)
        self.period_codes = ', '.join(p.code or '' for p in periods if p.code)
        self.period_month = periods[0].period_month or ''
        self.sl_qty_column_label = DMTB_SL_LABEL.get(nhom, nhom_label)

        seen_sx = set()
        Line = self.env['bao.cao.dinh.muc.vt.tb.line']
        self.line_ids.unlink()

        lines = []
        for period in periods:
            sx = period.company_sx_id
            if not sx:
                raise UserError(_(
                    'Kỳ "%(code)s" chưa có đơn vị sản xuất.',
                    code=period.code or period.display_name,
                ))
            if sx.id in seen_sx:
                raise UserError(_(
                    'Trùng đơn vị sản xuất "%(sx)s" trong các kỳ đã chọn.',
                    sx=sx.company_code or sx.name,
                ))
            seen_sx.add(sx.id)

            month_keys, row_metrics, plan_lines, nvl_lines = self._aggregate_period(
                period, linh_vuc_code,
            )
            if month_keys != column_keys:
                raise UserError(_(
                    'Kỳ "%(code)s" có dải tháng khác kỳ đầu tiên.',
                    code=period.code or period.display_name,
                ))
            if not plan_lines and not nvl_lines:
                raise UserError(_(
                    'Kỳ "%(code)s" (%(sx)s) không có dữ liệu cho nhóm "%(nhom)s".',
                    code=period.code or period.display_name,
                    sx=sx.company_code or sx.name,
                    nhom=nhom_label,
                ))
            if not any(c['sl_sp'] or c['sl_nvl'] for c in row_metrics):
                raise UserError(_(
                    'Kỳ "%(code)s" (%(sx)s) không có SL sản phẩm hoặc SL NVL '
                    'trong 3 tháng đầu cho nhóm "%(nhom)s".',
                    code=period.code or period.display_name,
                    sx=sx.company_code or sx.name,
                    nhom=nhom_label,
                ))

            lines.append({
                'wizard_id': self.id,
                'period_id': period.id,
                'nhom_linh_vuc': nhom,
                'company_sx_id': sx.id,
                'company_code': sx.company_code or sx.name or '',
                'metrics_json': json.dumps(row_metrics, ensure_ascii=False),
                'ghi_chu': ghi_chu_map.get((period.id, sx.id), ''),
            })

        if lines:
            Line.create(lines)

    def action_open_report(self):
        self.ensure_one()
        self._populate_lines()
        title = _('Định mức vật tư trung bình')
        if self.nhom_linh_vuc:
            title = _('%s — %s') % (title, self._nhom_label())
        if self.period_codes:
            title = _('%s (%s)') % (title, self.period_codes)
        return {
            'type': 'ir.actions.act_window',
            'name': title,
            'res_model': 'bao.cao.dinh.muc.vt.tb.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                'bao_cao_dmtb_wizard_id': self.id,
                'bao_cao_dmtb_columns': self.column_spec_json or '[]',
                'bao_cao_dmtb_sl_label': self.sl_qty_column_label or 'SL sản phẩm',
            },
        }

    def action_export_excel(self):
        self.ensure_one()
        if not self.line_ids:
            self._populate_lines()
        sl_label = self.sl_qty_column_label or 'SL sản phẩm'
        lines = self.line_ids
        if not lines:
            raise UserError(_('Không có dữ liệu để xuất Excel.'))

        try:
            column_spec = json.loads(self.column_spec_json or '[]')
        except (TypeError, ValueError):
            raise UserError(_('Không xác định được cột tháng hiển thị.'))
        if not column_spec:
            raise UserError(_('Không xác định được cột tháng hiển thị.'))

        wb = Workbook()
        ws = wb.active
        ws.title = 'Dinh muc VT TB'

        nguon_label = dict(self._fields['nguon_sl_sp'].selection).get(
            self.nguon_sl_sp, self.nguon_sl_sp
        )
        ws.cell(row=1, column=1, value='Báo cáo định mức vật tư trung bình')
        ws.cell(row=2, column=1, value='Kỳ')
        ws.cell(row=2, column=2, value=self.period_codes)
        ws.cell(row=3, column=1, value='Tháng kế hoạch')
        ws.cell(row=3, column=2, value=self.period_month or '')
        ws.cell(row=4, column=1, value='Nhóm')
        ws.cell(row=4, column=2, value=self._nhom_label())
        ws.cell(row=5, column=1, value='Nguồn')
        ws.cell(row=5, column=2, value=nguon_label)

        header_row1 = 7
        header_row2 = 8
        data_row = 9
        yellow = PatternFill(start_color='FFFF00', end_color='FFFF00', fill_type='solid')

        col = 1
        ws.merge_cells(
            start_row=header_row1, start_column=col,
            end_row=header_row2, end_column=col,
        )
        ws.cell(row=header_row1, column=col, value='Công ty')
        col += 1

        for col_def in column_spec:
            month_key = col_def.get('label') or col_def.get('month_key') or ''
            group_start = col
            ws.merge_cells(
                start_row=header_row1, start_column=group_start,
                end_row=header_row1, end_column=group_start + 2,
            )
            ws.cell(row=header_row1, column=group_start, value=month_key)
            for sub in (sl_label, 'SL NVL (kg)', 'Vật tư bình quân'):
                cell = ws.cell(row=header_row2, column=col, value=sub)
                if sub == 'Vật tư bình quân':
                    cell.fill = yellow
                col += 1

        ws.cell(row=header_row1, column=col, value='Ghi chú')
        ws.merge_cells(
            start_row=header_row1, start_column=col,
            end_row=header_row2, end_column=col,
        )
        ghi_chu_col = col
        max_col = col

        row_idx = data_row
        for line in lines.sorted(
            key=lambda l: (l.company_code or '').upper()
        ):
            ws.cell(row=row_idx, column=1, value=line.company_code)
            col_idx = 2
            for cell in line._metrics_list():
                sp = cell.get('sl_sp') or 0.0
                nvl = cell.get('sl_nvl') or 0.0
                dmbq = (nvl / sp) if sp else 0.0
                ws.cell(row=row_idx, column=col_idx, value=sp or None)
                col_idx += 1
                ws.cell(row=row_idx, column=col_idx, value=nvl or None)
                col_idx += 1
                cell_xl = ws.cell(row=row_idx, column=col_idx, value=dmbq or None)
                cell_xl.fill = yellow
                col_idx += 1
            ws.cell(row=row_idx, column=ghi_chu_col, value=line.ghi_chu or '')
            row_idx += 1

        self.env['ke.hoach.vat.tu']._apply_b5_export_style(
            ws, header_row1, header_row2, max_col,
            [(None, 'text')] * max_col,
            meta_rows=5,
        )
        ws.column_dimensions['A'].width = 14
        ws.column_dimensions[get_column_letter(ghi_chu_col)].width = 40

        output = io.BytesIO()
        wb.save(output)
        fname = 'DinhMucVT_TB.xlsx'
        attachment = self.env['ir.attachment'].sudo().create({
            'name': fname,
            'type': 'binary',
            'datas': base64.b64encode(output.getvalue()),
            'mimetype': (
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            ),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }


def _post_init_drop_dmtb_nhom_bao_cao(cr):
    cr.execute("DROP TABLE IF EXISTS dmtb_nhom_bao_cao_nganh_rel CASCADE")
    cr.execute("DROP TABLE IF EXISTS dmtb_nhom_bao_cao CASCADE")


class BaoCaoDinhMucVtTbLine(models.TransientModel):
    _name = 'bao.cao.dinh.muc.vt.tb.line'
    _description = 'Dòng báo cáo định mức vật tư trung bình'
    _order = 'company_code, id'

    wizard_id = fields.Many2one(
        'bao.cao.dinh.muc.vt.tb.wizard', ondelete='cascade', index=True)
    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ nguồn', readonly=True)
    nhom_linh_vuc = fields.Selection(
        DMTB_NHOM_SELECTION, string='Nhóm', readonly=True)
    company_sx_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', readonly=True)
    company_code = fields.Char(string='Công ty', index=True)
    metrics_json = fields.Text(string='Số liệu theo cột', readonly=True)
    ghi_chu = fields.Text(string='Ghi chú')

    nguon_sl_sp = fields.Selection(
        related='wizard_id.nguon_sl_sp', string='Nguồn', readonly=True)

    def _metrics_list(self):
        self.ensure_one()
        try:
            data = json.loads(self.metrics_json or '[]')
        except (TypeError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def write(self, vals):
        res = super().write(vals)
        if 'ghi_chu' in vals and not self.env.context.get('skip_dmtb_ghi_chu_sync'):
            self._sync_ghi_chu_to_master()
        return res

    def _sync_ghi_chu_to_master(self):
        GhiChu = self.env['dmtb.ghi.chu'].sudo()
        for rec in self:
            wizard = rec.wizard_id
            nhom = rec.nhom_linh_vuc or wizard.nhom_linh_vuc
            if not wizard or not nhom or not rec.period_id or not rec.company_sx_id:
                continue
            GhiChu._upsert_note(
                rec.period_id,
                nhom,
                wizard.nguon_sl_sp,
                rec.company_sx_id,
                rec.ghi_chu,
            )

    def action_export_excel(self):
        wizard = self[:1].wizard_id
        if not wizard:
            wizard_id = self.env.context.get('bao_cao_dmtb_wizard_id')
            if not wizard_id:
                raise UserError(_('Vui lòng xuất Excel từ một báo cáo đã mở.'))
            wizard = self.env['bao.cao.dinh.muc.vt.tb.wizard'].browse(wizard_id)
        wizard.ensure_one()
        return wizard.action_export_excel()
