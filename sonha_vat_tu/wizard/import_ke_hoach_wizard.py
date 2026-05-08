# -*- coding: utf-8 -*-
import base64
import io
import re
from markupsafe import Markup
from datetime import date
from openpyxl import load_workbook
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ImportKeHoachWizard(models.TransientModel):
    _name = 'import.ke.hoach.wizard'
    _description = 'Import kế hoạch thành phẩm từ Excel'

    period_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ',
        default=lambda self: self.env.context.get('active_id'))
    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')

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
        rec = Model.search(
            ['|', ('code', '=', raw), ('name', '=', raw)], limit=1)
        if not rec:
            rec = Model.search([('name', 'ilike', raw)], limit=1)
        return rec

    def action_import(self):
        self.ensure_one()
        if not self.file_data:
            raise UserError(_('Vui lòng chọn file Excel.'))

        try:
            wb = load_workbook(io.BytesIO(base64.b64decode(self.file_data)),
                               data_only=True, read_only=True)
        except Exception as exc:
            raise UserError(_('Không đọc được file Excel: %s') % exc)

        ws = wb.active
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        if not rows:
            raise UserError(_('File rỗng.'))

        header = [str(c).strip() if c is not None else '' for c in rows[0]]

        # Cố định: cột 0–3 Ngành/Dòng/Mã hàng/Mã SAP, từ cột 4 là Tháng M/YYYY
        MONTH_START_IDX = 4

        month_cols = []
        for idx in range(MONTH_START_IDX, len(header)):
            md = self._parse_month_header(header[idx])
            if md:
                month_cols.append((idx, md))
        if not month_cols:
            raise UserError(_(
                'Không tìm thấy cột tháng nào trong header. '
                'Mỗi cột tháng cần có dạng "Tháng M/YYYY", VD: Tháng 4/2026.'))

        Plan = self.env['ke.hoach.thanh.pham'].sudo()
        Bom = self.env['bom'].sudo()
        NganhHang = self.env['nganh.hang'].sudo()
        DongHang = self.env['dong.hang'].sudo()
        MaHang = self.env['ma.hang'].sudo()
        period = self.period_id
        company = period.company_id or self.env.company

        vals_list = []
        errors = []
        seen_keys = set()
        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = list(row) + [None] * (len(header) - len(row))
            nganh_raw = row[0]
            dong_raw = row[1]
            ma_hang = (row[2] or '').strip() if row[2] else ''
            ma_sap = str(row[3]).strip() if row[3] not in (None, '') else ''

            nganh_raw_s = str(nganh_raw).strip() if nganh_raw not in (None, '') else ''
            dong_raw_s = str(dong_raw).strip() if dong_raw not in (None, '') else ''

            if not nganh_raw_s:
                errors.append(_('Dòng %d: thiếu Ngành hàng.') % row_idx)
                continue
            if not dong_raw_s:
                errors.append(_('Dòng %d: thiếu Dòng hàng.') % row_idx)
                continue
            if not ma_hang:
                errors.append(_('Dòng %d: thiếu Mã hàng.') % row_idx)
                continue
            if not ma_sap:
                errors.append(_('Dòng %d: thiếu Mã SAP.') % row_idx)
                continue

            nganh = self._find_master('nganh.hang', nganh_raw_s)
            if not nganh:
                errors.append(_(
                    'Dòng %d: Ngành hàng "%s" không có trong danh mục.'
                ) % (row_idx, nganh_raw_s))
                continue

            dong = self._find_master('dong.hang', dong_raw_s)
            if not dong:
                errors.append(_(
                    'Dòng %d: Dòng hàng "%s" không có trong danh mục.'
                ) % (row_idx, dong_raw_s))
                continue

            if dong.nganh_hang_id != nganh:
                errors.append(_(
                    'Dòng %d: Dòng hàng "%s" không thuộc ngành "%s" trong danh mục.'
                ) % (row_idx, dong_raw_s, nganh_raw_s))
                continue

            ma_hang_rec = MaHang.search(
                [('code', '=', ma_hang), ('ma_sap', '=', ma_sap)], limit=1)
            if not ma_hang_rec:
                errors.append(_(
                    'Dòng %d: Mã hàng "%s" và Mã SAP "%s" không khớp một dòng trong '
                    'danh mục mã hàng.'
                ) % (row_idx, ma_hang, ma_sap))
                continue

            if ma_hang_rec.dong_hang_id != dong:
                errors.append(_(
                    'Dòng %d: Ngành/Dòng trên file không khớp danh mục mã hàng '
                    '(mã hàng %s / SAP %s).'
                ) % (row_idx, ma_hang, ma_sap))
                continue

            if ma_hang_rec.nganh_hang_id != nganh:
                errors.append(_(
                    'Dòng %d: Ngành hàng trên file không khớp danh mục mã hàng '
                    '(mã hàng %s / SAP %s).'
                ) % (row_idx, ma_hang, ma_sap))
                continue

            for col_idx, month_key in month_cols:
                raw_qty = row[col_idx]
                if raw_qty in (None, '', 0, 0.0):
                    continue
                try:
                    qty = float(raw_qty)
                except (TypeError, ValueError):
                    errors.append(_('Dòng %d, tháng %s: "%s" không phải số.')
                                  % (row_idx, month_key, raw_qty))
                    continue
                if qty == 0:
                    continue

                key = (company.id, ma_sap, month_key)
                if key in seen_keys:
                    errors.append(_(
                        'Dòng %d: trùng (Công ty/SAP/Tháng) trong file import.') % row_idx)
                    continue
                seen_keys.add(key)

                vals_list.append({
                    'period_id': period.id,
                    'company_id': company.id,
                    'nganh_hang_id': nganh.id,
                    'dong_hang_id': dong.id,
                    'ma_hang_id': ma_hang_rec.id,
                    'ma_hang': ma_hang_rec.code,
                    'ma_sap': ma_sap,
                    'month_key': month_key,
                    'qty': qty,
                })

        if vals_list:
            company_id = (period.company_id or self.env.company).id
            db_keys = {
                (r.ma_sap, r.month_key)
                for r in Plan.search([
                    ('period_id', '=', period.id),
                    ('company_id', '=', company_id),
                ])
            }
            for vals in vals_list:
                if (vals['ma_sap'], vals['month_key']) in db_keys:
                    errors.append(_(
                        'Đã tồn tại dữ liệu trong kỳ cho Mã SAP=%s, Tháng=%s.'
                    ) % (vals['ma_sap'], vals['month_key']))

        if errors:
            shown = errors[:80]
            msg = '\n'.join('- %s' % e for e in shown)
            if len(errors) > 80:
                msg += _('\n... còn %d lỗi khác.') % (len(errors) - 80)
            raise UserError(_('File import có lỗi, chưa ghi dữ liệu:\n%s') % msg)

        if vals_list:
            Plan.with_context(is_importing=True).create(vals_list)
            
            nganh_dict = {n.id: n.name for n in NganhHang.search([])}
            dong_dict = {d.id: d.name for d in DongHang.search([])}

            table_html = """
            <div class="table-responsive">
            <table class="table table-sm table-bordered o_main_table mb-0" style="font-size: 13px;">
                <thead class="bg-light">
                    <tr>
                        <th>Ngành hàng</th>
                        <th>Dòng hàng</th>
                        <th>Mã hàng</th>
                        <th>Mã SAP</th>
                        <th>Tháng</th>
                        <th class="text-end">Số lượng</th>
                    </tr>
                </thead>
                <tbody>
            """
            for vals in vals_list:
                nganh_hang_name = nganh_dict.get(vals.get('nganh_hang_id'), '')
                dong_hang_name = dong_dict.get(vals.get('dong_hang_id'), '')
                ma_hang = vals.get('ma_hang') or ''
                ma_sap = vals.get('ma_sap') or ''
                month_key = vals.get('month_key') or ''
                qty_val = vals.get('qty', 0.0)
                qty_str = "{:,.2f}".format(qty_val).replace(',', 'X').replace('.', ',').replace('X', '.')

                table_html += f"""
                    <tr>
                        <td>{nganh_hang_name}</td>
                        <td>{dong_hang_name}</td>
                        <td>{ma_hang}</td>
                        <td>{ma_sap}</td>
                        <td>{month_key}</td>
                        <td class="text-end">{qty_str}</td>
                    </tr>
                """
            table_html += """
                </tbody>
            </table>
            </div>
            """
            msg = Markup(f"<p class='mb-2'><b>Đã import {len(vals_list)} dòng từ file {self.file_name or '-'}</b></p>{table_html}")
            period.message_post(body=msg)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ke.hoach.vat.tu',
            'res_id': period.id,
            'view_mode': 'form',
            'target': 'current',
        }
