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

    def _find_by_code(self, model_name, code):
        code = self._clean_value(code)
        if not code:
            return False
        return self.env[model_name].search([('ma', '=', code)], limit=1)

    def action_import(self):
        self.ensure_one()

        if load_workbook is None:
            raise ValidationError(_('Thiếu thư viện openpyxl để đọc file Excel.'))

        if not self.file_data:
            raise ValidationError(_('Vui lòng chọn file Excel để import.'))

        workbook = load_workbook(filename=BytesIO(base64.b64decode(self.file_data)), data_only=True)
        sheet = workbook.active

        model = self.env['mdm.tong.hop']

        imported = 0
        updated = 0
        errors = []

        for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            ma_tg = self._clean_value(row[0] if len(row) > 0 else False)
            if not ma_tg:
                continue

            vals = {
                'ma_tg': ma_tg,
                'ma': self._clean_value(row[1] if len(row) > 1 else False),
                'mdm_hh_type_id': self._find_by_code('mdm.hh.type', row[2] if len(row) > 2 else False).id,
                'ten_ngan': self._clean_value(row[3] if len(row) > 3 else False),
                'ten': self._clean_value(row[4] if len(row) > 4 else False),
                'dvt': self._clean_value(row[5] if len(row) > 5 else False),
                'chung_loai1': self._find_by_code('mdm.chung.loai1', row[6] if len(row) > 6 else False).id,
                'chung_loai2': self._find_by_code('mdm.chung.loai2', row[7] if len(row) > 7 else False).id,
                'linh_vuc': self._find_by_code('mdm.linh.vuc', row[8] if len(row) > 8 else False).id,
                'nganh_hang': self._find_by_code('mdm.nganh.hang', row[9] if len(row) > 9 else False).id,
                'nhan_hang': self._find_by_code('mdm.nhan.hang', row[10] if len(row) > 10 else False).id,
                'chat_lieu': self._find_by_code('mdm.chat.lieu', row[11] if len(row) > 11 else False).id,
                'do_bong': self._find_by_code('mdm.do.bong', row[12] if len(row) > 12 else False).id,
                'do_day': self._find_by_code('mdm.do.day', row[13] if len(row) > 13 else False).id,
                'dung_tich': self._find_by_code('mdm.dung.tich', row[14] if len(row) > 14 else False).id,
            }

            try:
                existing = model.search([('ma_tg', '=', ma_tg)], limit=1)
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    model.create(vals)
                    imported += 1
            except Exception as exc:
                errors.append(_('Dòng %(row)s (Mã TG: %(ma_tg)s): %(error)s', row=row_index, ma_tg=ma_tg, error=str(exc)))

        message = _('Import hoàn tất. Tạo mới: %(new)s, Cập nhật: %(updated)s', new=imported, updated=updated)
        if errors:
            message = message + '\n' + '\n'.join(errors[:20])
            raise ValidationError(message)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Thành công'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }
