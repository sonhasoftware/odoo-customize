import base64
from io import BytesIO

from odoo import _, fields, models
from odoo.exceptions import ValidationError

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


class MDMTongHopImportWizard(models.TransientModel):
    _name = 'mdm.tong.hop.import.wizard'
    _description = 'Import MDM Hàng hóa từ Excel'

    file_data = fields.Binary(string='File Excel', required=True)
    file_name = fields.Char(string='Tên file')

    def _clean_value(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return str(value).strip() or False

    def _find_many2one_by_code(self, model_name, code, field_label):
        code = self._clean_value(code)
        if not code:
            return self.env[model_name].browse()
        record = self.env[model_name].search([('ma', '=', code)], limit=1)
        if record:
            return record
        raise ValidationError(_('Không tìm thấy dữ liệu ở field %(field)s với mã "%(code)s".', field=field_label, code=code))

    def action_import(self):
        self.ensure_one()

        if load_workbook is None:
            raise ValidationError(_('Thiếu thư viện openpyxl để đọc file Excel.'))

        if not self.file_data:
            raise ValidationError(_('Vui lòng chọn file Excel để import.'))

        workbook = load_workbook(filename=BytesIO(base64.b64decode(self.file_data)), data_only=True)
        sheet = workbook.active

        model = self.env['mdm.tong.hop']
        line_model = self.env['mdm.tong.hop.line']

        imported = 0
        updated = 0
        errors = []

        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        company_codes = set()
        for row in rows:
            if not any(self._clean_value(cell) for cell in row[:18]):
                continue
            company_code = self._clean_value(row[0] if len(row) > 0 else False)
            if company_code:
                company_codes.add(company_code)

        if len(company_codes) > 1:
            raise ValidationError(_('File không cùng 1 mã công ty. Vui lòng kiểm tra lại cột mã công ty trong file import.'))

        if not company_codes:
            raise ValidationError(_('Thiếu mã công ty trong file import.'))

        company_code = next(iter(company_codes))
        company = self.env['res.company'].search([('company_code', '=', company_code)], limit=1)
        if not company:
            raise ValidationError(_('Không tìm thấy công ty với mã công ty "%(code)s".', code=company_code))

        for row_index, row in enumerate(rows, start=2):
            ma_tg = self._clean_value(row[1] if len(row) > 1 else False)
            ma_mdm = self._clean_value(row[2] if len(row) > 2 else False)

            if not any(self._clean_value(cell) for cell in row[:18]):
                continue

            vals = {
                'ma_tg': ma_tg,
                'ma': ma_mdm,
                'mdm_hh_type_id': self._find_many2one_by_code('mdm.hh.type', row[3] if len(row) > 3 else False, 'Loại hàng hóa').id,
                'ten_ngan': self._clean_value(row[4] if len(row) > 4 else False),
                'ten': self._clean_value(row[5] if len(row) > 5 else False),
                'dvt': self._clean_value(row[6] if len(row) > 6 else False),
                'chung_loai1': self._find_many2one_by_code('mdm.chung.loai1', row[7] if len(row) > 7 else False, 'Chủng loại 1').id,
                'chung_loai2': self._find_many2one_by_code('mdm.chung.loai2', row[8] if len(row) > 8 else False, 'Chủng loại 2').id,
                'linh_vuc': self._find_many2one_by_code('mdm.linh.vuc', row[9] if len(row) > 9 else False, 'Lĩnh vực').id,
                'nganh_hang': self._find_many2one_by_code('mdm.nganh.hang', row[10] if len(row) > 10 else False, 'Ngành hàng').id,
                'nhan_hang': self._find_many2one_by_code('mdm.nhan.hang', row[11] if len(row) > 11 else False, 'Nhãn hàng').id,
                'chat_lieu': self._find_many2one_by_code('mdm.chat.lieu', row[12] if len(row) > 12 else False, 'Chất liệu').id,
                'do_bong': self._find_many2one_by_code('mdm.do.bong', row[13] if len(row) > 13 else False, 'Độ bóng').id,
                'do_day': self._find_many2one_by_code('mdm.do.day', row[14] if len(row) > 14 else False, 'Độ dày').id,
                'dung_tich_plus': self._clean_value(row[15] if len(row) > 15 else False),
                'dvt_dung_tich': self._clean_value(row[16] if len(row) > 16 else False),
                'bom_sale': self._find_many2one_by_code('bom.sale', row[17] if len(row) > 17 else False, 'Loại trong BOM sales').id,
            }

            try:
                if not ma_mdm:
                    raise ValidationError(_('Thiếu Mã MDM ở cột C.'))

                existing = model.search([('ma', '=', ma_mdm)], limit=1)

                if existing:
                    parent_record = existing
                    parent_record.sudo().write(dict(vals, dvcs=company.id))
                    updated += 1
                else:
                    parent_record = model.create(dict(vals, dvcs=company.id))
                    imported += 1

                line_model.create({
                    'tong_hop_id': parent_record.id,
                    'ma_mdm': ma_mdm,
                    'ma_dv': ma_tg,
                    'dvcs': company.id,
                })
            except Exception as exc:
                errors.append(_('Dòng %(row)s (Mã MDM: %(ma_mdm)s): %(error)s', row=row_index, ma_mdm=ma_mdm or '-', error=str(exc)))

        message = _('Import hoàn tất. Tạo mới: %(new)s, Cập nhật: %(updated)s', new=imported, updated=updated)
        if errors:
            message = message + '\n' + '\n'.join(errors[:20])
            raise ValidationError(message)

        return {'type': 'ir.actions.act_window_close'}
