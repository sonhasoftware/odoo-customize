# -*- coding: utf-8 -*-
import re
from collections import Counter
from datetime import date

from markupsafe import Markup

from odoo import fields, models, _
from odoo.exceptions import UserError


class ImportKeHoachWizard(models.TransientModel):
    _name = 'import.ke.hoach.wizard'
    _description = 'Import ke hoach tu Excel'
    _inherit = ['vat.tu.excel.mixin']

    period_id = fields.Many2one('ke.hoach.vat.tu', string='Kỳ SX')
    kinh_doanh_id = fields.Many2one('ke.hoach.kinh.doanh', string='KHKD')
    import_type = fields.Selection([
        ('business', 'Kế hoạch kinh doanh'),
        ('production', 'Kế hoạch sản xuất'),
    ], string='Loại import', required=True,
        default=lambda self: self.env.context.get('default_import_type', 'business'))
    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Ten file')

    MONTH_RE = re.compile(r'(\d{1,2})\s*[/\-]\s*(\d{4})')
    _IMPORT_CTX = {'is_importing': True, 'tracking_disable': True}
    _WRITE_FIELDS = ('company_id', 'ma_hang', 'qty_t0', 'qty_t1', 'qty_t2', 'qty_t3', 'sequence')
    _PLAN_HEADERS = ['Đơn vị đặt hàng', 'Ngành hàng', 'Tên hàng', 'Mã hàng', 'Mã']
    COL_MA_HANG, COL_MA_SAP = 3, 4
    HEADER_ROW_IDX = 5
    MONTH_START_COL = 5

    def _is_business(self):
        return self.import_type == 'business'

    def _plan_record(self):
        self.ensure_one()
        return self.kinh_doanh_id if self._is_business() else self.period_id

    def _plan_code(self):
        rec = self._plan_record()
        return rec.code if rec else ''

    def _plan_month(self):
        rec = self._plan_record()
        return rec.period_month if rec else ''

    def _plan_company_sx_code(self):
        rec = self._plan_record()
        if not rec or not self._is_business():
            return ''
        return (rec.company_sx_id.company_code or rec.company_sx_id.name or '').strip()

    def _horizon_months(self):
        rec = self._plan_record()
        if not rec:
            return []
        if self._is_business():
            return rec._get_horizon_months()
        return rec._get_horizon_months()

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

    def _read_workbook(self):
        rows = [
            tuple(row)
            for row in self._load_workbook().active.iter_rows(values_only=True)
        ]
        if not rows:
            raise UserError(_('File rỗng.'))
        return rows

    def _norm_text(self, value):
        return str(value or '').strip()

    def _validate_metadata(self, rows):
        if len(rows) < 6:
            raise UserError(_(
                'File Excel không đúng mẫu. Vui lòng tải lại template từ gói/kỳ đang mở.'))

        meta = {}
        for row_idx in range(3):
            row = rows[row_idx] if row_idx < len(rows) else ()
            label = self._norm_text(row[0] if len(row) > 0 else '')
            value = self._norm_text(row[1] if len(row) > 1 else '')
            meta[label.lower()] = value

        code = meta.get('mã') or meta.get('ma')
        month = meta.get('tháng bắt đầu') or meta.get('thang bat dau')

        errors = []
        if not code:
            errors.append(_('Mã không được để trống. Vui lòng kiểm tra ô B1.'))
        elif code != (self._plan_code() or ''):
            errors.append(_(
                'Mã trong file là "%s", không đúng với bản ghi đang mở "%s".'
            ) % (code, self._plan_code() or ''))

        if not month:
            errors.append(_('Tháng bắt đầu không được để trống. Vui lòng kiểm tra ô B2.'))
        elif month != (self._plan_month() or ''):
            errors.append(_(
                'Tháng bắt đầu trong file là "%s", không đúng với bản ghi đang mở "%s".'
            ) % (month, self._plan_month() or ''))

        if self._is_business():
            sx_label = meta.get('đơn vị sản xuất') or meta.get('don vi san xuat')
            if not sx_label:
                errors.append(_(
                    'Đơn vị sản xuất không được để trống. Vui lòng kiểm tra ô B3.'
                ))
            elif sx_label != (self._plan_company_sx_code() or ''):
                errors.append(_(
                    'Đơn vị sản xuất trong file là "%s", không đúng với bản ghi đang mở "%s".'
                ) % (sx_label, self._plan_company_sx_code() or ''))

        self._raise_errors(errors)

    def _prepare_rows(self, rows):
        header_row_idx = self.HEADER_ROW_IDX
        header = [str(c).strip() if c is not None else '' for c in rows[header_row_idx]]
        for col_idx, expected in enumerate(self._PLAN_HEADERS):
            actual = header[col_idx] if col_idx < len(header) else ''
            if actual.lower() != expected.lower():
                raise UserError(_(
                    'File Excel không đúng mẫu: cột %s phải là "%s" (đang là "%s"). '
                    'Vui lòng tải lại template.'
                ) % (col_idx + 1, expected, actual or '—'))
        month_col_by_key = {}
        horizon_months = self._horizon_months()
        month_offset_map = {month: idx for idx, month in enumerate(horizon_months)}
        for idx, label in enumerate(header):
            month_key = self._parse_month_header(label)
            if month_key and idx >= self.MONTH_START_COL and month_key in month_offset_map:
                month_col_by_key[month_key] = idx
        if not month_col_by_key:
            raise UserError(_(
                'Không tìm thấy cột tháng hợp lệ trong bảng dữ liệu. '
                'Vui lòng kiểm tra dòng tiêu đề số 6.'))
        month_cols = [
            (month_col_by_key.get(month_key), month_key, month_offset_map[month_key])
            for month_key in horizon_months
        ]
        return header, month_cols, header_row_idx + 1

    def _build_company_lookup(self):
        by_code = {}
        by_name = {}
        for company in self.env['res.company'].sudo().search([]):
            code = self._norm_text(company.company_code)
            name = self._norm_text(company.name)
            if code:
                by_code[code.lower()] = company
            if name:
                by_name[name.lower()] = company
        return by_code, by_name

    def _resolve_company_cached(self, raw, row_idx, errors, company_lookup):
        text = self._norm_text(raw)
        if not text:
            errors.append(_('Dòng %d: thiếu Đơn vị.') % row_idx)
            return self.env['res.company']
        by_code, by_name = company_lookup
        company = by_code.get(text.lower()) or by_name.get(text.lower())
        if not company:
            errors.append(_('Dòng %d: không tìm thấy Đơn vị "%s".') % (row_idx, text))
            return self.env['res.company']
        return company

    def _parse_qty_value(self, raw_qty, row_idx, month_key, errors):
        if raw_qty is None:
            return 0.0
        if isinstance(raw_qty, str):
            text = raw_qty.strip()
            if not text:
                return 0.0
            raw_qty = text.replace(',', '.')
        if isinstance(raw_qty, bool):
            return float(int(raw_qty))
        if isinstance(raw_qty, (int, float)):
            return float(raw_qty)
        try:
            return float(raw_qty)
        except (TypeError, ValueError):
            errors.append(_('Dòng %d, tháng %s: "%s" không phải số.') % (row_idx, month_key, raw_qty))
            return 0.0

    def _parse_qty_row(self, row, row_idx, month_cols, errors):
        qty_by_offset = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
        for col_idx, month_key, offset in month_cols:
            if col_idx is None:
                qty_by_offset[offset] = 0.0
                continue
            raw_qty = row[col_idx] if col_idx < len(row) else None
            qty_by_offset[offset] = self._parse_qty_value(raw_qty, row_idx, month_key, errors)
        return qty_by_offset

    def _collect_import_sap_codes(self, rows, header, data_start_idx):
        codes = set()
        for row in rows[data_start_idx:]:
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            ma_sap = row[self.COL_MA_SAP]
            if ma_sap not in (None, ''):
                codes.add(str(ma_sap).strip())
        return codes

    @staticmethod
    def _row_changed(existing, vals, fields):
        if existing.sequence != vals.get('sequence', existing.sequence):
            return True
        if 'company_id' in fields:
            existing_company = existing.company_id.id if existing.company_id else False
            if existing_company != vals.get('company_id'):
                return True
        return any((existing[f] or 0.0) != (vals.get(f) or 0.0) for f in fields if f.startswith('qty_')) or any(
            (getattr(existing, f, '') or '') != (vals.get(f) or '')
            for f in fields if not f.startswith('qty_') and f not in ('sequence', 'company_id')
        )

    @staticmethod
    def _assign_import_sequences(vals_list):
        for idx, vals in enumerate(vals_list, start=1):
            vals['sequence'] = idx * 10

    def _validate_plan_row(self, row_idx, row, errors, company_lookup, mdm_codes):
        company_rec = self._resolve_company_cached(row[0], row_idx, errors, company_lookup)
        if not company_rec:
            return None

        ma_hang = row[self.COL_MA_HANG]
        ma_sap = row[self.COL_MA_SAP]
        ma_hang = str(ma_hang).strip() if ma_hang not in (None, '') else ''
        ma_sap = str(ma_sap).strip() if ma_sap not in (None, '') else ''

        if not ma_sap:
            errors.append(_('Dòng %d: thiếu Mã.') % row_idx)
            return None
        if ma_sap not in mdm_codes:
            errors.append(_(
                'Dòng %d: Mã "%s" không tồn tại.'
            ) % (row_idx, ma_sap))
            return None

        return {
            'company_id': company_rec.id,
            'ma_hang': ma_hang,
            'ma_sap': ma_sap,
        }

    def _collect_plan_rows(self, rows, header, month_cols, data_start_idx, extra_vals=None):
        errors = []
        vals_list = []
        company_lookup = self._build_company_lookup()
        mdm_codes = self.env['ma.hang'].get_mdm_sap_codes_set(
            self._collect_import_sap_codes(rows, header, data_start_idx),
        )

        for row_idx, row in enumerate(rows[data_start_idx:], start=data_start_idx + 1):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            base_vals = self._validate_plan_row(row_idx, row, errors, company_lookup, mdm_codes)
            if not base_vals:
                continue

            qty_by_offset = self._parse_qty_row(row, row_idx, month_cols, errors)
            vals_list.append({
                **base_vals,
                **(extra_vals or {}),
                'qty_t0': qty_by_offset[0],
                'qty_t1': qty_by_offset[1],
                'qty_t2': qty_by_offset[2],
                'qty_t3': qty_by_offset[3],
            })

        self._raise_errors(errors)
        self._assign_import_sequences(vals_list)
        return vals_list

    def _split_create_update(self, Plan, vals_list, domain):
        """Khớp dòng file với DB theo thứ tự STT — cho phép trùng (Đơn vị, Mã)."""
        existing = Plan.search(domain, order='sequence, id')
        to_create, to_update = [], []
        for idx, vals in enumerate(vals_list):
            if idx < len(existing):
                line = existing[idx]
                write_vals = {f: vals[f] for f in self._WRITE_FIELDS if f in vals}
                if self._row_changed(line, vals, self._WRITE_FIELDS):
                    to_update.append((line.id, write_vals))
            else:
                to_create.append(vals)
        to_delete = existing[len(vals_list):]
        return existing, to_create, to_update, to_delete

    def _write_plan_rows(self, Plan, to_create, to_update):
        if to_update:
            Plan._sql_bulk_import_update(to_update)
        if to_create:
            Plan.with_context(**self._IMPORT_CTX).create(to_create)

    def _raise_errors(self, errors):
        self._raise_import_errors(
            errors, header=_('File Excel có lỗi, chưa ghi dữ liệu:'))

    def _check_access(self):
        allowed = (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu')
            or self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        )
        if not allowed:
            label = 'kế hoạch kinh doanh' if self._is_business() else 'kế hoạch sản xuất'
            raise UserError(_('Bạn không có quyền import %s.') % label)

    def action_import(self):
        self.ensure_one()
        self._check_access()
        is_business = self._is_business()
        label = 'kế hoạch kinh doanh' if is_business else 'kế hoạch sản xuất'

        if is_business:
            if not self.kinh_doanh_id:
                raise UserError(_('Thiếu kế hoạch kinh doanh.'))
            if self.kinh_doanh_id.locked:
                raise UserError(_('Kế hoạch kinh doanh đã lấy vào sản xuất, không thể import lại.'))
        else:
            if not self.period_id:
                raise UserError(_('Thiếu kỳ kế hoạch sản xuất.'))
            if self.period_id.state != 'ke_hoach':
                raise UserError(_(
                    'Kỳ kế hoạch đã sang bước sau, không thể import lại kế hoạch sản xuất.'))
            if self.period_id.co_ke_hoach_vat_tu:
                raise UserError(_(
                    'Đã tạo kế hoạch vật tư, không thể import lại kế hoạch sản xuất.'))

        rows = self._read_workbook()
        self._validate_metadata(rows)
        header, month_cols, data_start_idx = self._prepare_rows(rows)

        count = (
            self._import_business(rows, header, month_cols, data_start_idx)
            if is_business else
            self._import_production(rows, header, month_cols, data_start_idx)
        )

        attachment = self.env['ir.attachment'].sudo().create({
            'name': self.file_name or 'ke_hoach_import.xlsx',
            'type': 'binary',
            'datas': self.file_data,
            'res_model': self.kinh_doanh_id._name if is_business else 'ke.hoach.vat.tu',
            'res_id': self.kinh_doanh_id.id if is_business else self.period_id.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        target = self.kinh_doanh_id if is_business else self.period_id
        scope = 'kd' if is_business else 'sx'
        target.with_context(vat_tu_chatter_scope=scope).message_post(body=Markup(
            '<p><b>Đã import %s dòng %s từ file %s.</b></p>' %
            (count, label, self.file_name or '-')
        ), attachment_ids=[attachment.id])

        if is_business:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'ke.hoach.kinh.doanh',
                'res_id': self.kinh_doanh_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ke.hoach.vat.tu',
            'res_id': self.period_id.id,
            'view_mode': 'form',
            'views': [(self.env.ref('sonha_vat_tu.view_ke_hoach_vat_tu_form_sx').sudo().id, 'form')],
            'context': {'vat_tu_chatter_scope': scope},
            'target': 'current',
        }

    def _import_business(self, rows, header, month_cols, data_start_idx):
        Plan = self.env['ke.hoach.kinh.doanh.line'].sudo()
        vals_list = self._collect_plan_rows(
            rows, header, month_cols, data_start_idx,
            extra_vals={'kinh_doanh_id': self.kinh_doanh_id.id},
        )
        domain = [('kinh_doanh_id', '=', self.kinh_doanh_id.id)]
        _existing, to_create, to_update, to_delete = self._split_create_update(
            Plan, vals_list, domain,
        )
        if to_delete:
            to_delete.with_context(**self._IMPORT_CTX).unlink()
        self._write_plan_rows(Plan, to_create, to_update)
        return len(vals_list)

    def _check_business_rows_covered(self, vals_list):
        kd_lines = self.env['ke.hoach.kinh.doanh.line'].sudo().search([
            ('kinh_doanh_id.period_sx_id', '=', self.period_id.id),
            ('ma_sap', '!=', False),
        ])
        if not kd_lines:
            return

        kd_counts = Counter(
            (line.company_id.id, line.ma_sap) for line in kd_lines
        )
        file_counts = Counter(
            (v['company_id'], v['ma_sap']) for v in vals_list
        )
        missing = sorted(
            (company_id, ma_sap, need - file_counts.get((company_id, ma_sap), 0))
            for (company_id, ma_sap), need in kd_counts.items()
            if file_counts.get((company_id, ma_sap), 0) < need
        )
        if not missing:
            return

        company_label = {
            c.id: c.company_code or c.name
            for c in self.env['res.company'].sudo().browse({cid for cid, _ma, _n in missing})
        }
        errors = [
            _(
                'Thiếu %d dòng kế hoạch kinh doanh Đơn vị=%s, Mã=%s. '
                'Nếu không sản xuất, giữ dòng và nhập Số lượng = 0.'
            ) % (shortage, company_label.get(company_id, company_id), ma_sap)
            for company_id, ma_sap, shortage in missing[:20]
        ]
        if len(missing) > 20:
            errors.append(
                _('... còn %d nhóm (Đơn vị + Mã) bị thiếu dòng.') % (len(missing) - 20))
        self._raise_errors(errors)

    def _import_production(self, rows, header, month_cols, data_start_idx):
        Plan = self.env['ke.hoach.san.xuat'].sudo()
        company_sx = self.env.company

        vals_list = self._collect_plan_rows(
            rows, header, month_cols, data_start_idx,
            extra_vals={
                'period_id': self.period_id.id,
                'company_sx_id': company_sx.id,
            },
        )
        self._check_business_rows_covered(vals_list)

        domain = [('period_id', '=', self.period_id.id)]
        _existing, to_create, to_update, to_delete = self._split_create_update(
            Plan, vals_list, domain,
        )
        if to_delete:
            to_delete.with_context(**self._IMPORT_CTX).unlink()

        self._write_plan_rows(Plan, to_create, to_update)
        return len(vals_list)
