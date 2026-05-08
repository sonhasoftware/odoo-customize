# -*- coding: utf-8 -*-
import base64
import io

from openpyxl import load_workbook
from odoo import _, fields, models
from odoo.exceptions import UserError


class ImportBomWizard(models.TransientModel):
    _name = 'import.bom.wizard'
    _description = 'Import BOM từ Excel'

    company_id = fields.Many2one('res.company', string='Đơn vị', default=lambda self: self.env.company)
    file_data = fields.Binary(string='File Excel')
    file_name = fields.Char(string='Tên file')

    def _to_float_or_error(self, raw, field_label, row_idx, errors):
        if raw in (None, ''):
            return 0.0
        try:
            return float(raw)
        except (TypeError, ValueError):
            errors.append(_('Dòng %d: cột %s không phải số (%s).') % (row_idx, field_label, raw))
            return None

    def action_import(self):
        self.ensure_one()
        Bom = self.env['bom'].sudo()
        MaHang = self.env['ma.hang'].sudo()
        if not self.file_data:
            raise UserError(_('Vui lòng chọn file Excel.'))

        try:
            wb = load_workbook(io.BytesIO(base64.b64decode(self.file_data)), data_only=True, read_only=True)
        except Exception as exc:
            raise UserError(_('Không đọc được file Excel: %s') % exc)

        ws = wb.active
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        if not rows:
            raise UserError(_('File rỗng.'))

        errors = []
        vals_list = []
        seen = set()
       
        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or not any(c not in (None, '') for c in row):
                continue
            raw = list(row)
            while raw and raw[-1] in (None, ''):
                raw.pop()
            if len(raw) == 8:
                raw = [None] + raw
            row = (raw + [None] * 9)[:9]

            ma_bom = (str(row[0]).strip() if row[0] not in (None, '') else '')
            ma_tp = (str(row[1]).strip() if row[1] not in (None, '') else '')
            ten_tp = (str(row[2]).strip() if row[2] not in (None, '') else '')
            ma_nvl = (str(row[3]).strip() if row[3] not in (None, '') else '')
            ten_nvl = (str(row[4]).strip() if row[4] not in (None, '') else '')
            if not ma_tp or not ma_nvl:
                errors.append(_('Dòng %d: thiếu Mã TP hoặc Mã NVL.') % row_idx)
                continue
            if not ma_bom:
                ma_bom = ma_tp

            key = (self.company_id.id, ma_bom, ma_nvl)
            if key in seen:
                errors.append(_('Dòng %d: trùng bộ (Đơn vị, Mã BOM, Mã NVL) trong file.') % row_idx)
                continue
            seen.add(key)

            sl_dinh_muc = self._to_float_or_error(row[5], 'Số lượng định mức / 1 sản phẩm', row_idx, errors)
            do_day = self._to_float_or_error(row[6], 'Độ dày', row_idx, errors)
            kho_1 = self._to_float_or_error(row[7], 'Khổ 1', row_idx, errors)
            kho_2 = self._to_float_or_error(row[8], 'Khổ 2', row_idx, errors)
            if None in (sl_dinh_muc, do_day, kho_1, kho_2):
                continue

            vals_list.append({
                'company_id': self.company_id.id,
                'ma_bom': ma_bom,
                'ma_tp': ma_tp,
                'ten_tp': ten_tp or ma_tp,
                'ma_nvl': ma_nvl,
                'ten_nvl': ten_nvl or ma_nvl,
                'sl_dinh_muc': sl_dinh_muc,
                'do_day': do_day,
                'kho_1': kho_1,
                'kho_2': kho_2,
            })

        if vals_list:
            nvl_codes = sorted({v['ma_nvl'] for v in vals_list if v.get('ma_nvl')})
            nvl_master = MaHang.search([('ma_nvl', 'in', nvl_codes)])
            nvl_map = {r.ma_nvl: r for r in nvl_master if r.ma_nvl}
            for vals in vals_list:
                master = nvl_map.get(vals['ma_nvl'])
                if not master:
                    errors.append(_('Mã NVL %s chưa có trong danh mục Mã hàng.') % vals['ma_nvl'])
                    continue
                if master.ten_nvl:
                    vals['ten_nvl'] = master.ten_nvl

            existing = Bom.search([
                ('company_id', '=', self.company_id.id),
                ('ma_bom', 'in', [v['ma_bom'] for v in vals_list]),
                ('ma_nvl', 'in', [v['ma_nvl'] for v in vals_list]),
            ])
            existing_keys = {(r.company_id.id, r.ma_bom, r.ma_nvl) for r in existing}
            for vals in vals_list:
                if (vals['company_id'], vals['ma_bom'], vals['ma_nvl']) in existing_keys:
                    errors.append(_('Đã tồn tại BOM cho Đơn vị=%s, Mã BOM=%s, Mã NVL=%s.')
                                  % (self.company_id.display_name, vals['ma_bom'], vals['ma_nvl']))

        if errors:
            raise UserError(_('File import có lỗi, chưa ghi dữ liệu:\n- %s') % '\n- '.join(errors[:100]))

        if vals_list:
            Bom.create(vals_list)

        return {'type': 'ir.actions.act_window_close'}
