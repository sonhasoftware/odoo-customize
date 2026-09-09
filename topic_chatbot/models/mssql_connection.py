# -*- coding: utf-8 -*-
from odoo import models, fields, api
from . import crypto_utils

class MssqlConnection(models.Model):
    _name = 'topic_chatbot.mssql_connection'
    _description = 'SQL Server Connection'

    name = fields.Char(string='Connection Name', required=True, help='Tên mô tả kết nối (VD: Máy chủ Kế Toán)')
    active = fields.Boolean(string='Active', default=True)
    
    host = fields.Char(string='SQL Server Host', required=True, default='localhost')
    port = fields.Char(string='Port', default='1433')
    database = fields.Char(string='Database Name', required=True)
    user = fields.Char(string='Username')
    password = fields.Char(string='Password')
    driver = fields.Char(string='ODBC Driver', default='ODBC Driver 17 for SQL Server')

    def write(self, vals):
        if 'password' in vals and vals.get('password') and not crypto_utils.is_encrypted(vals['password']):
            vals['password'] = crypto_utils.encrypt_value(self.env, vals['password'])
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('password') and not crypto_utils.is_encrypted(vals['password']):
                vals['password'] = crypto_utils.encrypt_value(self.env, vals['password'])
        return super().create(vals_list)

    def read(self, fields=None, load='_classic_read'):
        res = super().read(fields, load)
        if fields and 'password' in fields:
            for record in res:
                if record.get('password'):
                    record['password'] = crypto_utils.decrypt_value(self.env, record['password'])
        return res

    def action_test_connection(self):
        self.ensure_one()
        host = self.host or 'localhost'
        port = self.port or '1433'
        db = self.database or ''
        user = self.user or ''
        # Trực tiếp lấy từ thuộc tính self.password (đã qua override read() decrypt ở UI, 
        # nhưng trong backend ORM read object không gọi read(). Phải giải mã tự động).
        # Tốt nhất gọi decrypt trên raw field database.
        raw_pw = self.password or ''
        password = crypto_utils.decrypt_value(self.env, raw_pw) if crypto_utils.is_encrypted(raw_pw) else raw_pw
        driver = self.driver or 'ODBC Driver 17 for SQL Server'

        try:
            conn = None
            connector_used = ""
            
            try:
                import pyodbc
                if '\\' in host or '/' in host:
                    server_str = host.replace('/', '\\')
                else:
                    port_str = f",{port}" if port and str(port).strip() not in ("1433", "") else ""
                    server_str = f"{host}{port_str}"

                auth_str = f"UID={user};PWD={password};" if user else "Trusted_Connection=yes;"

                drivers_to_try = [driver] if driver else []
                try:
                    installed = pyodbc.drivers()
                    for d in installed:
                        if 'sql server' in d.lower() and d not in drivers_to_try:
                            drivers_to_try.append(d)
                except Exception:
                    pass

                if 'SQL Server' not in drivers_to_try:
                    drivers_to_try.append('SQL Server')

                last_err = None
                for drv in drivers_to_try:
                    try:
                        conn_str = (
                            f"DRIVER={{{drv}}};SERVER={server_str};DATABASE={db};"
                            f"{auth_str}TrustServerCertificate=yes;Connection Timeout=10;"
                        )
                        conn = pyodbc.connect(conn_str, timeout=10)
                        connector_used = f"pyodbc ({drv})"
                        break
                    except Exception as ex_drv:
                        last_err = ex_drv

                if not conn and last_err:
                    err_pyodbc = str(last_err)
            except ImportError:
                pass

            if not conn:
                try:
                    import pymssql
                    port_int = int(port) if port and str(port).isdigit() else 1433
                    conn = pymssql.connect(
                        server=host, port=port_int, user=user, password=password, database=db, login_timeout=10
                    )
                    connector_used = "pymssql"
                except ImportError:
                    if 'err_pyodbc' in locals():
                        raise Exception(f"pyodbc báo lỗi: {err_pyodbc}. Chưa cài pymssql.")
                    else:
                        raise Exception("Chưa cài thư viện kết nối (pyodbc/pymssql).")
                except Exception as e_pymssql:
                    raise Exception(f"pymssql báo lỗi: {str(e_pymssql)}")

            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION")
                row = cursor.fetchone()
                version_info = row[0] if row else 'N/A'
                conn.close()

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Thành Công',
                        'message': f"Đã kết nối {self.name} qua {connector_used}.\n{version_info[:80]}...",
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi Kết Nối',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
