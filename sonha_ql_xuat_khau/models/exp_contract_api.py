from odoo import api, fields, models
import psycopg2
import requests
import json
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class ExpContractApi(models.Model):
    _name = 'exp.contract.api'

    url = fields.Char(string="URL API", store=True)
    user = fields.Char(string="Tên đăng nhập", store=True)
    password = fields.Char(string="Mật khẩu", store=True)
    error = fields.Char(string="Lỗi", store=True)
    code = fields.Char(string="Mã API", store=True)

    def download_data(self, rec, contract_no, time):
        date_from = time.strftime('%Y%m%d')
        time = time.strftime('%H%M%S')

        url_api = str(rec.url).format(date_from=date_from, time=time, contract_no=contract_no)

        username = str(rec.user)
        password = str(rec.password)

        try:
            response = requests.get(url_api, auth=(username, password), verify=False)
            if response.status_code == 200:
                data = response.json().get('d', {}).get('results', [])

                query = """
                UPDATE so_sap_storage s
                SET is_active = False
                FROM json_to_recordset(%s::json) AS t(
                    "BSTKD_ANA" text,
                    "KUNNR" text,
                    "MATNR" text,
                    "ARKTX" text,
                    "VRKME" text,
                    "VBELN" text,
                    "DATE_DOC" text,
                    "KWMENG" text,
                    "UMREZ" text,
                    "UMREN" text
                )
                WHERE s.so_number = t."VBELN"
                AND s.shipment_date = to_date(t."DATE_DOC", 'YYYYMMDD');
                
                INSERT INTO so_sap_storage (contract_no, customer_code, product_code, product_name, unit, so_number, shipment_date, quantity, cay_uom, ton_uom, is_active)
                SELECT 
                    t."BSTKD_ANA",
                    t."KUNNR",
                    t."MATNR",
                    t."ARKTX",
                    t."VRKME",
                    t."VBELN",
                    to_date(t."DATE_DOC", 'YYYYMMDD'),
                    t."KWMENG",
                    t."UMREZ",
                    t."UMREN",
                    True
                FROM json_to_recordset(%s::json) AS t(
                    "BSTKD_ANA" text,
                    "KUNNR" text,
                    "MATNR" text,
                    "ARKTX" text,
                    "VRKME" text,
                    "VBELN" text,
                    "DATE_DOC" text,
                    "KWMENG" text,
                    "UMREZ" text,
                    "UMREN" text
                )
                """

                self.env.cr.execute(query, (json.dumps(data), json.dumps(data)))
                self.error = ""
            else:
                self.error = f"Lỗi API: {response.status_code} - {response.reason}"
        except requests.exceptions.ConnectionError:
            self.error = "Không thể kết nối tới máy chủ API. Vui lòng kiểm tra mạng hoặc URL."
        except requests.exceptions.Timeout:
            self.error = "Kết nối đến API bị hết thời gian chờ. Vui lòng thử lại sau."
        except requests.exceptions.RequestException as e:
            self.error = f"Lỗi yêu cầu API: {str(e)}"
        except ValueError:
            self.error = "Lỗi xử lý dữ liệu JSON trả về từ API."
        except psycopg2.Error as db_error:
            self.error = f"Lỗi cơ sở dữ liệu: {str(db_error).splitlines()[0]}"
        except Exception as e:
            self.error = f"Lỗi không xác định: {str(e).splitlines()[0]}"

    def cron_get_data(self):
        self.with_delay().action_download()

    def action_download(self):
        contract_no = ''
        now = datetime.now() + timedelta(hours=7) - timedelta(hours=1)
        self.download_data(self, contract_no, now)


class SoSapStorage(models.Model):
    _name = 'so.sap.storage'

    contract_no = fields.Char(string="Số hợp đồng", store=True)
    customer_code = fields.Char(string="Mã khách hàng", store=True)
    shipment_date = fields.Date(string="Ngày xuất hàng", store=True)
    product_code = fields.Char(string="Mã hàng hóa", store=True)
    product_name = fields.Char(string="Tên hàng hóa", store=True)
    quantity = fields.Char(string="Số lượng", store=True)
    unit = fields.Char(string="Đơn vị tính", store=True)
    so_number = fields.Char(string="Số SO", store=True)
    is_active = fields.Boolean(store=True)
    cay_uom = fields.Char(store=True)
    ton_uom = fields.Char(store=True)

