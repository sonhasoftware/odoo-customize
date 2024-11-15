from odoo import api, fields, models
import requests


class Inventory(models.Model):
    _name = 'inventory'

    plant = fields.Char(string="Plant")
    sloc_code = fields.Char(string="Mã Sloc")
    sloc_name = fields.Char(string="Tên Sloc")
    product_code = fields.Char(string="Mã hàng")
    product_name = fields.Char(string="Tên hàng")
    quantity = fields.Float(string="Số lượng tồn", digits=(7, 3))
    unit = fields.Char(string="Đơn vị tính")
    batch = fields.Char(string="Lô Batch")

    def fetch_and_create_records(self):
        # URL của API
        url = "https://erpprd.sonha.com.vn/sap/opu/odata/SAP/ZO_API_TK_DMS_SRV/TK_DMSSet"

        # Tham số cho request
        params = {
            '$filter': "(MAR eq '10000017' and PLANT eq '*' and SLOG eq '*')",
            'sap-client': '100',
            '$format': 'json'
        }

        # Thông tin xác thực cho Basic Auth
        username = "API_OD2"  # Thay bằng username thực tế
        password = "Init@12345"  # Thay bằng password thực tế

        try:
            # Gửi yêu cầu GET với Basic Auth
            response = requests.get(url, params=params, auth=(username, password))

            # Kiểm tra phản hồi của API
            if response.status_code == 200:
                data = response.json().get('d', {}).get('results', [])
                self.search([]).unlink()
                # Duyệt qua từng bản ghi và tạo trong bảng Odoo
                for record in data:
                    self.create({
                        'plant': record.get('WERKS'),
                        'sloc_code': record.get('LGORT'),
                        'sloc_name': record.get('LGOBE'),
                        'product_code': record.get('MATNR'),
                        'product_name': record.get('MAKTX'),
                        'quantity': record.get('MENGE'),
                        'unit': record.get('MEINS'),
                        'batch': record.get('CHARG')
                    })
                return True
            else:
                # Thông báo nếu phản hồi không thành công
                return {"error": f"Không thể lấy dữ liệu từ API, status code: {response.status_code}"}

        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
