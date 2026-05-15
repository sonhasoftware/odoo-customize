import base64
from io import BytesIO

from odoo import _, fields, models
from odoo.exceptions import ValidationError

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


class MDMKhachHangImportWizard(models.TransientModel):
    _name = 'mdm.khach.hang.import.wizard'
    _description = 'Import MDM Khách hàng từ Excel'

    file_data = fields.Binary(string='File Excel', required=True)
    file_name = fields.Char(string='Tên file')

    def _clean_value(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return str(value).strip() or False

    def _find_or_create_by_name(self, model_name, value):
        name = self._clean_value(value)
        if not name:
            return self.env[model_name].browse()

        record = self.env[model_name].search([('ten', '=', name)], limit=1)
        if record:
            return record

        return self.env[model_name].create({'ten': name, 'ma': name})

    def _find_or_create_salesman(self, code):
        code = self._clean_value(code)
        if not code:
            return self.env['mdm.saleman'].browse()

        record = self.env['mdm.saleman'].search([('ma', '=', code)], limit=1)
        if record:
            return record

        return self.env['mdm.saleman'].create({'ma': code, 'ten': code})

    def action_import(self):
        self.ensure_one()

        if load_workbook is None:
            raise ValidationError(_('Thiếu thư viện openpyxl để đọc file Excel.'))

        if not self.file_data:
            raise ValidationError(_('Vui lòng chọn file Excel để import.'))

        workbook = load_workbook(filename=BytesIO(base64.b64decode(self.file_data)), data_only=True)
        sheet = workbook.active
        model = self.env['mdm.khach.hang']

        imported = 0
        updated = 0
        errors = []

        for row_index, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            ma_khach = self._clean_value(row[0] if len(row) > 0 else False)
            ten_khach = self._clean_value(row[1] if len(row) > 1 else False)
            if not ma_khach and not ten_khach:
                continue

            try:
                vals = {
                    'ma_khach': ma_khach,
                    'ten_khach': ten_khach,
                    'dia_chi_khach': self._clean_value(row[2] if len(row) > 2 else False),
                    'phuong_xa_cu': self._find_or_create_by_name('phuong.xa.cu', row[3] if len(row) > 3 else False).id,
                    'quan_huyen_cu': self._find_or_create_by_name('quan.huyen.cu', row[4] if len(row) > 4 else False).id,
                    'tinh_cu': self._find_or_create_by_name('tinh.cu', row[5] if len(row) > 5 else False).id,
                    'dat_nuoc': self._find_or_create_by_name('mdm.quoc.gia', row[6] if len(row) > 6 else False).id,
                    'so_dien_thoai': self._clean_value(row[7] if len(row) > 7 else False),
                    'mst': self._clean_value(row[8] if len(row) > 8 else False),
                    'plan': self._find_or_create_by_name('mdm.plan', row[9] if len(row) > 9 else False).id,
                    'ma_cn': self._find_or_create_by_name('mdm.chi.nhanh', row[10] if len(row) > 10 else False).id,
                    'nhom_khach': self._find_or_create_by_name('mdm.nhom.khach', row[11] if len(row) > 11 else False).id,
                    'dvcs': self.env.company.id,
                    'ten_salesman': self._find_or_create_salesman(row[13] if len(row) > 13 else False).id,
                    'vung': self._clean_value(row[14] if len(row) > 14 else False),
                    'qlv': self._find_or_create_by_name('mdm.quan.ly.vung', row[15] if len(row) > 15 else False).id,
                    'khu_vuc': self._find_or_create_by_name('mdm.khu.vuc', row[16] if len(row) > 16 else False).id,
                    'mien_lon': self._find_or_create_by_name('mien.lon', row[17] if len(row) > 17 else False).id,
                    'mien_nho': self._find_or_create_by_name('mien.nho', row[18] if len(row) > 18 else False).id,
                }

                existing = model.search([('ma_khach', '=', ma_khach)], limit=1) if ma_khach else model.browse()
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    model.create(vals)
                    imported += 1
            except Exception as exc:
                errors.append(_('Dòng %(row)s: %(error)s', row=row_index, error=str(exc)))

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
