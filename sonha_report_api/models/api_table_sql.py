import psycopg2
from odoo import api, fields, models
import requests
import json
from datetime import datetime, timedelta
from datetime import time
import logging
_logger = logging.getLogger(__name__)


class APITableSQL(models.Model):
    _name = 'api.table.sql'

    url = fields.Char(string="URL API", required=True)
    user = fields.Char(string="Tên đăng nhập", required=True)
    password = fields.Char(string="Mật khẩu", required=True)
    table = fields.Char(string="Tên database", required=True)
    error = fields.Char("Lỗi")
    job = fields.Boolean("Chạy tự động")
    start_time = fields.Float("Giờ bắt đầu")
    end_time = fields.Float("Giờ kết thúc")

    def cron_data(self):
        self.with_delay().cron_data_api_download()

    def cron_data_api_download(self):
        list_api = self.env['api.table.sql'].sudo().search([('job', '=', True)])
        for r in list_api:
            now = datetime.now() + timedelta(hours=7)
            hours = int(r.start_time)
            minutes = int((r.start_time - hours) * 60)
            seconds = int(((r.start_time - hours) * 60 - minutes) * 60)
            start_time = time(hour=hours, minute=minutes, second=seconds)

            hours_end_time = int(r.end_time)
            minutes_end_time = int((r.end_time - hours_end_time) * 60)
            seconds_end_time = int(((r.end_time - hours_end_time) * 60 - minutes_end_time) * 60)
            end_time = time(hour=hours_end_time, minute=minutes_end_time, second=seconds_end_time)
            if start_time <= now.time() <= end_time:
                url = str(r.url)
                username = str(r.user)
                password = str(r.password)
                table = str(r.table)
                try:
                    response = requests.get(url, auth=(username, password), verify=False)
                    if response.status_code == 200:
                        data = response.json().get('d', {}).get('results', [])
                        table_name = table.lower()
                        self.create_table_if_not_exists(table_name)
                        self.create_dynamic_fields(table_name, data)
                        self.insert_data(table_name, data)
                        r.error = ""
                    else:
                        r.error = f"Lỗi API: {response.status_code} - {response.reason}"
                except requests.exceptions.ConnectionError:
                    r.error = "Không thể kết nối tới máy chủ API. Vui lòng kiểm tra mạng hoặc URL."
                except requests.exceptions.Timeout:
                    r.error = "Kết nối đến API bị hết thời gian chờ. Vui lòng thử lại sau."
                except requests.exceptions.RequestException as e:
                    r.error = f"Lỗi yêu cầu API: {str(e)}"
                except ValueError:
                    r.error = "Lỗi xử lý dữ liệu JSON trả về từ API."
                except psycopg2.Error as db_error:
                    r.error = f"Lỗi cơ sở dữ liệu: {str(db_error).splitlines()[0]}"
                except Exception as e:
                    r.error = f"Lỗi không xác định: {str(e).splitlines()[0]}"


    def action_download(self):
        url = str(self.url)
        username = str(self.user)
        password = str(self.password)
        table = str(self.table)
        try:
            response = requests.get(url, auth=(username, password), verify=False)
            if response.status_code == 200:
                data = response.json().get('d', {}).get('results', [])
                table_name = table.lower()
                self.create_table_if_not_exists(table_name)
                self.create_dynamic_fields(table_name, data)
                self.insert_data(table_name, data)
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

    def create_table_if_not_exists(self, table_name):
        """Tạo bảng nếu chưa tồn tại"""
        cr = self._cr
        cr.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY
            );
        """)
        self._cr.commit()

    def create_dynamic_fields(self, table_name, data):
        """Tự động tạo field trong bảng nếu chưa tồn tại."""

        cr = self._cr  # Lấy cursor để thực thi SQL
        existing_columns = {}

        # 🔹 Lấy danh sách các cột hiện có trong bảng
        cr.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s;
        """, (table_name,))

        for row in cr.fetchall():
            existing_columns[row[0].lower()] = True  # Chuyển về chữ thường để tránh lỗi tên cột

        for record in data:  # Lặp qua từng dictionary trong danh sách
            for key, value in record.items():
                column_name = key.lower()  # Chuyển key thành chữ thường để tránh lỗi

                if column_name not in existing_columns:
                    field_type = "TEXT"  # Mặc định kiểu dữ liệu là TEXT

                    if isinstance(value, int):
                        field_type = "INTEGER"
                    elif isinstance(value, float):
                        field_type = "DOUBLE PRECISION"
                    elif isinstance(value, bool):
                        field_type = "BOOLEAN"

                    # 🔹 Thêm cột mới nếu chưa tồn tại
                    cr.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {field_type};")
                    existing_columns[column_name] = True  # Đánh dấu cột đã thêm

        self._cr.commit()

    def insert_data(self, table_name, data):
        """Chèn dữ liệu vào bảng Odoo với các cột mới (hỗ trợ nhiều bản ghi)."""

        if not isinstance(data, list):
            raise ValueError("Dữ liệu đầu vào phải là danh sách chứa các dictionary!")

        self._cr.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s;
            """, (table_name,))
        existing_columns = {row[0] for row in self._cr.fetchall()}

        if "create_date" not in existing_columns:
            self._cr.execute(f"ALTER TABLE {table_name} ADD COLUMN create_date TIMESTAMP;")
            self._cr.commit()
            existing_columns.add("create_date")

        for record in data:  # Lặp từng dictionary trong danh sách
            processed_data = {}

            for key, value in record.items():
                # Chuẩn hóa các trường id (viết hoa hoặc viết thường đều xử lý chung một cách)
                if key.lower() == 'id':  # Dùng 'id' để chuẩn hóa tất cả
                    key = 'id'
                key = key.lower()

                if isinstance(value, dict):
                    processed_data[key] = json.dumps(value)  # Chuyển dict sang JSON string
                elif isinstance(value, str) and value.strip() == "":
                    processed_data[key] = None  # Chuyển giá trị rỗng thành NULL
                else:
                    processed_data[key] = value

            # Nếu không có `id`, tự động sinh ra `id` theo thứ tự tăng dần
            if "id" not in processed_data or processed_data["id"] is None:
                self._cr.execute(f"SELECT COALESCE(MAX(id), 0) + 1 FROM {table_name};")
                processed_data["id"] = self._cr.fetchone()[0]
            if "create_date" not in processed_data:
                processed_data["create_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Xây dựng câu lệnh INSERT
            keys = ", ".join(processed_data.keys())
            values = ", ".join(["%s"] * len(processed_data))

            sql = f"INSERT INTO {table_name} ({keys}) VALUES ({values});"
            self._cr.execute(sql, tuple(processed_data.values()))

        self._cr.commit()
