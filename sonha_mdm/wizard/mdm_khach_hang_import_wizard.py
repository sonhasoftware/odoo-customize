from odoo import fields, models
from odoo.exceptions import ValidationError
import base64
import io
from openpyxl import load_workbook


class MDMKhachHangImportWizard(models.TransientModel):
    _name = 'mdm.khach.hang.import.wizard'
    _description = 'Import MDM Khach Hang'

    file = fields.Binary("File Excel", required=True)
    filename = fields.Char("Tên file")

    def _clean_value(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return str(value).strip()

    def _get_m2o_by_code(self, model_name, code):
        if not code:
            return False
        record = self.env[model_name].sudo().search([('ma', '=', code)], limit=1)
        if not record:
            raise ValidationError(f"Không tìm thấy mã '{code}' trong model {model_name}.")
        return record.id

    def action_import(self):
        self.ensure_one()
        workbook = load_workbook(filename=io.BytesIO(base64.b64decode(self.file)), data_only=True)
        sheet = workbook.active

        header_map = {
            'mã tg': 'ma_khach',
            'ma tg': 'ma_khach',
            'id': 'ma_dms',
            'tên ngắn': 'ten_khach',
            'ten ngan': 'ten_khach',
            'tên đầy đủ': 'dia_chi_khach',
            'ten day du': 'dia_chi_khach',
            'đvt': 'ma_cn',
            'dvt': 'ma_cn',
            'chủng loại 1': 'nhom_khach',
            'chung loai 1': 'nhom_khach',
            'chủng loại 2': 'ten_salesman',
            'chung loai 2': 'ten_salesman',
            'lĩnh vực': 'ma_tinh',
            'linh vuc': 'ma_tinh',
            'ngành hàng': 'dat_nuoc',
            'nganh hang': 'dat_nuoc',
            'nhãn hàng': 'khu_vuc',
            'nhan hang': 'khu_vuc',
            'chất liệu': 'qlv',
            'chat lieu': 'qlv',
            'độ bóng': 'mien_lon',
            'do bong': 'mien_lon',
            'độ dày': 'mien_nho',
            'do day': 'mien_nho',
            'đvt thể tích': 'plan',
            'dvt the tich': 'plan',
        }

        many2one_model_map = {
            'ma_cn': 'mdm.chi.nhanh',
            'nhom_khach': 'mdm.nhom.khach',
            'ten_salesman': 'mdm.saleman',
            'ma_tinh': 'mdm.tinh',
            'dat_nuoc': 'mdm.quoc.gia',
            'khu_vuc': 'mdm.khu.vuc',
            'qlv': 'mdm.quan.ly.vung',
            'plan': 'mdm.plan',
            'mien_lon': 'mien.lon',
            'mien_nho': 'mien.nho',
        }

        headers = []
        for col in range(1, sheet.max_column + 1):
            cell = sheet.cell(row=1, column=col).value
            headers.append((cell or '').strip().lower() if isinstance(cell, str) else '')

        processed = 0
        for row_idx in range(2, sheet.max_row + 1):
            values = {}
            is_empty = True
            for col_idx, header in enumerate(headers, start=1):
                field_name = header_map.get(header)
                if not field_name:
                    continue
                raw_value = self._clean_value(sheet.cell(row=row_idx, column=col_idx).value)
                if raw_value:
                    is_empty = False
                if field_name in many2one_model_map:
                    values[field_name] = self._get_m2o_by_code(many2one_model_map[field_name], raw_value)
                else:
                    values[field_name] = raw_value

            if is_empty:
                continue

            ma_tg = values.get('ma_khach')
            if not ma_tg:
                raise ValidationError(f"Dòng {row_idx} thiếu 'Mã TG'.")

            existed = self.env['mdm.khach.hang'].sudo().search([('ma_khach', '=', ma_tg)], limit=1)
            if existed:
                existed.write(values)
            else:
                if not values.get('ten_khach'):
                    values['ten_khach'] = ma_tg
                if not values.get('so_dien_thoai'):
                    values['so_dien_thoai'] = '0000000000'
                self.env['mdm.khach.hang'].sudo().create(values)
            processed += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import thành công',
                'message': f'Đã xử lý {processed} dòng dữ liệu.',
                'type': 'success',
                'sticky': False,
            }
        }
