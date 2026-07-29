# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

# Template: Mã TP | Tên TP | Mã NVL | Tên NVL | SL định mức | SL SPĐM | Độ dày | Khổ 1 | Khổ 2
COL_COUNT = 9
UPDATE_FIELDS = ('sl_dinh_muc', 'sl_spdm', 'do_day', 'kho_1', 'kho_2')


class ImportBomWizard(models.TransientModel):
    _name = 'import.bom.wizard'
    _description = 'Import BOM từ Excel'
    _inherit = ['vat.tu.excel.mixin']

    DATA_START_ROW = 2
    ERROR_LIMIT = 100

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

    def _parse_rows(self, rows):
        errors = []
        vals_list = []
        seen = set()

        for row_idx, row in enumerate(rows, start=self.DATA_START_ROW):
            if not row or not any(c not in (None, '') for c in row):
                continue
            row = (list(row) + [None] * COL_COUNT)[:COL_COUNT]

            def text(col):
                return str(row[col]).strip() if row[col] not in (None, '') else ''

            ma_tp, ten_tp = text(0), text(1)
            ma_nvl, ten_nvl = text(2), text(3)
            if not ma_tp or not ma_nvl:
                errors.append(_('Dòng %d: thiếu Mã TP hoặc Mã NVL.') % row_idx)
                continue

            key = (ma_tp, ma_nvl)
            if key in seen:
                errors.append(_('Dòng %d: trùng bộ (Mã TP, Mã NVL) trong file.') % row_idx)
                continue
            seen.add(key)

            sl_dinh_muc = self._to_float_or_error(row[4], 'Số lượng định mức', row_idx, errors)
            sl_spdm = self._to_float_or_error(row[5], 'Số lượng SPĐM', row_idx, errors)
            do_day = self._to_float_or_error(row[6], 'Độ dày', row_idx, errors)
            kho_1 = self._to_float_or_error(row[7], 'Khổ 1', row_idx, errors)
            kho_2 = self._to_float_or_error(row[8], 'Khổ 2', row_idx, errors)
            if None in (sl_dinh_muc, sl_spdm, do_day, kho_1, kho_2):
                continue

            vals_list.append({
                'ma_tp': ma_tp,
                'ten_tp': ten_tp or ma_tp,
                'ma_nvl': ma_nvl,
                'ten_nvl': ten_nvl or ma_nvl,
                'sl_dinh_muc': sl_dinh_muc,
                'sl_spdm': sl_spdm or 1.0,
                'do_day': do_day,
                'kho_1': kho_1,
                'kho_2': kho_2,
            })

        return vals_list, errors

    def _fill_ten_nvl_from_catalog(self, vals_list):
        names = {
            rec.ma_sap: rec.ten_hang
            for rec in self.env['ma.hang'].sudo().search([
                ('ma_sap', 'in', list({v['ma_nvl'] for v in vals_list})),
            ])
            if rec.ma_sap and rec.ten_hang
        }
        for vals in vals_list:
            if names.get(vals['ma_nvl']):
                vals['ten_nvl'] = names[vals['ma_nvl']]

    def _apply_rows(self, vals_list):
        Bom = self.env['bom'].sudo()
        existing_map = {
            (rec.ma_tp, rec.ma_nvl): rec.id
            for rec in Bom.search([
                ('ma_tp', 'in', [v['ma_tp'] for v in vals_list]),
                ('ma_nvl', 'in', [v['ma_nvl'] for v in vals_list]),
            ])
        }

        to_create = []
        to_update = []
        for vals in vals_list:
            bom_id = existing_map.get((vals['ma_tp'], vals['ma_nvl']))
            if bom_id:
                to_update.append((bom_id, vals))
            else:
                to_create.append(vals)

        if to_update:
            params = [self.env.uid, [bom_id for bom_id, _vals in to_update]]
            params += [
                [vals[fname] for _bom_id, vals in to_update]
                for fname in UPDATE_FIELDS
            ]
            self.env.cr.execute("""
                UPDATE bom AS b SET
                    sl_dinh_muc = data.sl_dinh_muc,
                    sl_spdm = data.sl_spdm,
                    do_day = data.do_day,
                    kho_1 = data.kho_1,
                    kho_2 = data.kho_2,
                    write_uid = %s,
                    write_date = NOW() AT TIME ZONE 'UTC'
                FROM (
                    SELECT unnest(%s::int[]) AS id,
                           unnest(%s::numeric[]) AS sl_dinh_muc,
                           unnest(%s::numeric[]) AS sl_spdm,
                           unnest(%s::numeric[]) AS do_day,
                           unnest(%s::numeric[]) AS kho_1,
                           unnest(%s::numeric[]) AS kho_2
                ) AS data
                WHERE b.id = data.id
            """, params)
            Bom.browse([bom_id for bom_id, _vals in to_update]).invalidate_recordset(
                list(UPDATE_FIELDS) + ['write_uid', 'write_date'])
        if to_create:
            Bom.create(to_create)

        return len(to_create), len(to_update)

    def action_import(self):
        self.ensure_one()
        rows = self._read_data_rows()
        if not rows:
            raise UserError(_('File Excel không có dòng dữ liệu (từ dòng 2).'))

        vals_list, errors = self._parse_rows(rows)
        # Chỉ ghi sau khi cả file đã sạch lỗi.
        self._raise_import_errors(errors, header=_('File import có lỗi, chưa ghi dữ liệu:'))
        if not vals_list:
            raise UserError(_('File Excel không có dòng dữ liệu hợp lệ.'))

        self._fill_ten_nvl_from_catalog(vals_list)
        self._apply_rows(vals_list)
        return {'type': 'ir.actions.act_window_close'}
