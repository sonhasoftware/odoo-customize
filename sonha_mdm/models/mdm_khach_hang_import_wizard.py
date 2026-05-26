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

    def _find_many2one_by_code(self, model_name, value, field_label):
        code = self._clean_value(value)
        if not code:
            return self.env[model_name].browse()

        record = self.env[model_name].search([('ma', '=', code)], limit=1)
        if record:
            return record

        raise ValidationError(_('Không tìm thấy dữ liệu ở field %(field)s với mã "%(code)s".', field=field_label, code=code))

    @staticmethod
    def _merge_non_empty_vals(existing_record, incoming_vals):
        merged_vals = {}
        for field_name, value in incoming_vals.items():
            if value not in (False, None, ''):
                merged_vals[field_name] = value
            elif existing_record:
                merged_vals[field_name] = existing_record[field_name]
        return merged_vals

    def action_import(self):
        self.ensure_one()

        if load_workbook is None:
            raise ValidationError(_('Thiếu thư viện openpyxl để đọc file Excel.'))

        if not self.file_data:
            raise ValidationError(_('Vui lòng chọn file Excel để import.'))

        workbook = load_workbook(filename=BytesIO(base64.b64decode(self.file_data)), data_only=True)
        sheet = workbook.active
        model = self.env['mdm.khach.hang']
        line_model = self.env['mdm.khach.hang.line']

        imported = 0
        updated = 0
        errors = []

        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        company_codes = set()
        for row in rows:
            if not any(self._clean_value(cell) for cell in row[:20]):
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
            if not any(self._clean_value(cell) for cell in row[:20]):
                continue

            ma_kh_ncc = self._clean_value(row[1] if len(row) > 1 else False)
            ma_mdm = self._clean_value(row[2] if len(row) > 2 else False)

            try:
                if not ma_mdm:
                    raise ValidationError(_('Thiếu Mã MDM ở cột C.'))

                vals = {
                    'ma_khach': ma_kh_ncc,
                    'ma': ma_mdm,
                    'ten_khach': self._clean_value(row[3] if len(row) > 3 else False),
                    'dia_chi_khach': self._clean_value(row[4] if len(row) > 4 else False),
                    'phuong_xa_cu': self._find_many2one_by_code('phuong.xa.cu', row[5] if len(row) > 5 else False, 'Phường/xã cũ').id,
                    'quan_huyen_cu': self._find_many2one_by_code('quan.huyen.cu', row[6] if len(row) > 6 else False, 'Quận/huyện cũ').id,
                    'tinh_cu': self._find_many2one_by_code('tinh.cu', row[7] if len(row) > 7 else False, 'Tỉnh cũ').id,
                    'dat_nuoc': self._find_many2one_by_code('mdm.quoc.gia', row[8] if len(row) > 8 else False, 'Quốc gia').id,
                    'so_dien_thoai': self._clean_value(row[9] if len(row) > 9 else False),
                    'mst': self._clean_value(row[10] if len(row) > 10 else False),
                    'plan': self._find_many2one_by_code('mdm.plan', row[11] if len(row) > 11 else False, 'Plant').id,
                    'ma_cn': self._find_many2one_by_code('mdm.chi.nhanh', row[12] if len(row) > 12 else False, 'CN/NPP').id,
                    'nhom_khach': self._find_many2one_by_code('mdm.nhom.khach', row[13] if len(row) > 13 else False, 'Nhóm KH_NCC').id,
                    'ten_salesman': self._find_many2one_by_code('mdm.saleman', row[14] if len(row) > 14 else False, 'Mã_salesman').id,
                    'vung': self._clean_value(row[15] if len(row) > 15 else False),
                    'qlv': self._find_many2one_by_code('mdm.quan.ly.vung', row[16] if len(row) > 16 else False, 'Quản lý vùng').id,
                    'khu_vuc': self._find_many2one_by_code('mdm.khu.vuc', row[17] if len(row) > 17 else False, 'Khu vực').id,
                    'mien_lon': self._find_many2one_by_code('mien.lon', row[18] if len(row) > 18 else False, 'Miền lớn').id,
                    'mien_nho': self._find_many2one_by_code('mien.nho', row[19] if len(row) > 19 else False, 'Miền nhỏ').id,
                }

                existing = model.search([('ma', '=', ma_mdm)], limit=1)
                if existing:
                    parent_record = existing
                    update_vals = self._merge_non_empty_vals(existing, vals)
                    parent_record.write(dict(update_vals, dvcs=company.id))
                    updated += 1
                else:
                    parent_record = model.create(dict(vals, dvcs=company.id))
                    imported += 1

                line_vals = {
                    'khach_hang_id': parent_record.id,
                    'ma_mdm': ma_mdm,
                    'dvcs': company.id,
                }
                if ma_kh_ncc:
                    line_vals['ma_dv'] = ma_kh_ncc
                line_model.create(line_vals)
            except Exception as exc:
                errors.append(_('Dòng %(row)s (Mã MDM: %(ma_mdm)s): %(error)s', row=row_index, ma_mdm=ma_mdm or '-', error=str(exc)))

        message = _('Import hoàn tất. Tạo mới: %(new)s, Cập nhật: %(updated)s', new=imported, updated=updated)
        if errors:
            message = message + '\n' + '\n'.join(errors[:20])
            raise ValidationError(message)

        return {'type': 'ir.actions.act_window_close'}
