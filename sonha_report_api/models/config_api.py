from odoo import api, fields, models
import requests
import json


class ConfigAPI(models.Model):
    _name = 'config.api'

    url = fields.Char(string="URL API", required=True)
    user = fields.Char(string="Tên đăng nhập", required=True)
    password = fields.Char(string="Mật khẩu", required=True)

    def action_download(self):
        url = str(self.url)

        # Thông tin xác thực cho Basic Auth
        username = str(self.user)
        password = str(self.password)

        response = requests.get(url, auth=(username, password), verify=False)

        # Kiểm tra phản hồi của API
        if response.status_code == 200:
            data = response.json().get('d', {}).get('results', [])
            table_name = "data_sap"
            self.create_dynamic_fields(table_name, data)
            self.insert_data(table_name, data)

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

        for record in data:  # Lặp từng dictionary trong danh sách
            processed_data = {}

            for key, value in record.items():
                # Chuẩn hóa các trường id (viết hoa hoặc viết thường đều xử lý chung một cách)
                if key.lower() == 'id':  # Dùng 'id' để chuẩn hóa tất cả
                    key = 'id'

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

            # Xây dựng câu lệnh INSERT
            keys = ", ".join(processed_data.keys())
            values = ", ".join(["%s"] * len(processed_data))

            sql = f"INSERT INTO {table_name} ({keys}) VALUES ({values});"
            self._cr.execute(sql, tuple(processed_data.values()))

        self._cr.commit()

