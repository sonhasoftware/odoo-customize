from odoo import api, fields, models
import requests


class Inventory(models.Model):
    _name = 'inventory'

    plant = fields.Char(string="Plant")
    sloc_code = fields.Char(string="Mã Sloc")
    sloc_name = fields.Char(string="Tên Sloc")
    product_code = fields.Char(string="Mã hàng")
    product_name = fields.Char(string="Tên hàng")
    quantity = fields.Float(string="Số lượng tồn")
    unit = fields.Char(string="Đơn vị tính")
    batch = fields.Char(string="Lô Batch")

    def fetch_and_create_records(self):
        # URL của API
        url = "https://erpprd.sonha.com.vn/sap/opu/odata/SAP/ZO_API_TK_DMS_SRV/TK_DMSSet?$filter=(MAR eq '*' and PLANT eq '2201' and SLOG eq '*') &sap-client=100&$format=json"

        # Thông tin xác thực cho Basic Auth
        username = "API_OD2"
        password = "Init@12345"

        try:
            # Gửi yêu cầu GET với Basic Auth
            response = requests.get(url, auth=(username, password))

            # Kiểm tra phản hồi của API
            if response.status_code == 200:
                data = response.json().get('d', {}).get('results', [])
                self.sudo().search([('plant', '=', '2201')]).unlink()
                # Duyệt qua từng bản ghi và tạo trong bảng Odoo
                for record in data:
                    self.sudo().create({
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

    def fetch_and_create_inventory_records(self):
        # URL của API
        url = "https://erpprd.sonha.com.vn/sap/opu/odata/SAP/ZO_API_TK_DMS_SRV/TK_DMSSet?$filter=(MAR eq '*' and PLANT eq '2202' and SLOG eq '*') &sap-client=100&$format=json"

        # Thông tin xác thực cho Basic Auth
        username = "API_OD2"
        password = "Init@12345"

        try:
            # Gửi yêu cầu GET với Basic Auth
            response = requests.get(url, auth=(username, password))

            # Kiểm tra phản hồi của API
            if response.status_code == 200:
                data = response.json().get('d', {}).get('results', [])
                self.sudo().search([('plant', '=', '2202')]).unlink()
                # Duyệt qua từng bản ghi và tạo trong bảng Odoo
                for record in data:
                    self.sudo().create({
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
