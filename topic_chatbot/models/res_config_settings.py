# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    DEPRECATED_GEMINI_MODEL_MAP = {
        'gemini-1.5-flash': 'gemini-3.5-flash-lite',
        'gemini-1.5-pro': 'gemini-3.1-pro-preview',
        'gemini-2.0-flash': 'gemini-3.6-flash',
        'gemini-2.0-flash-001': 'gemini-3.6-flash',
        'gemini-2.0-flash-lite': 'gemini-3.5-flash-lite',
        'gemini-2.0-flash-lite-001': 'gemini-3.5-flash-lite',
    }

    topic_chatbot_gemini_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='topic_chatbot.gemini_api_key'
    )
    topic_chatbot_gemini_model = fields.Selection([
        ('gemini-3.6-flash', 'Gemini 3.6 Flash'),
        ('gemini-3.5-flash', 'Gemini 3.5 Flash'),
        ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite'),
        ('gemini-3.1-flash-lite', 'Gemini 3.1 Flash-Lite'),
        ('gemini-3.1-pro-preview', 'Gemini 3.1 Pro Preview'),
        ('gemini-2.5-flash', 'Gemini 2.5 Flash (Deprecated Oct 2026)'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro (Deprecated Oct 2026)'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash (Shutdown - auto migrate)'),
        ('gemini-1.5-flash', 'Gemini 1.5 Flash (Shutdown - auto migrate)'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro (Shutdown - auto migrate)'),
    ], string='Gemini Model',
        config_parameter='topic_chatbot.gemini_model',
        default='gemini-3.6-flash',
        help="Select the Gemini model for the chatbot."
    )
    topic_chatbot_stop_words = fields.Char(
        string='Custom Stop Words',
        config_parameter='topic_chatbot.stop_words',
        help="Comma-separated custom stop words to ignore during RAG search (e.g., xin, chao, giup)."
    )
    topic_chatbot_embedding_model = fields.Char(
        string='Embedding Model',
        config_parameter='topic_chatbot.embedding_model',
        default='gemini-embedding-2',
        help="Gemini text embedding model for Vector RAG Semantic Search."
    )
    topic_chatbot_mssql_enabled = fields.Boolean(
        string='Bật kết nối SQL Server',
        config_parameter='topic_chatbot.mssql_enabled',
        default=False
    )
    topic_chatbot_mssql_host = fields.Char(
        string='SQL Server Host',
        config_parameter='topic_chatbot.mssql_host',
        default='localhost'
    )
    topic_chatbot_mssql_port = fields.Char(
        string='SQL Server Port',
        config_parameter='topic_chatbot.mssql_port',
        default='1433'
    )
    topic_chatbot_mssql_db = fields.Char(
        string='Database Name',
        config_parameter='topic_chatbot.mssql_db'
    )
    topic_chatbot_mssql_user = fields.Char(
        string='SQL Server User',
        config_parameter='topic_chatbot.mssql_user'
    )
    topic_chatbot_mssql_password = fields.Char(
        string='SQL Server Password',
        config_parameter='topic_chatbot.mssql_password'
    )
    topic_chatbot_mssql_driver = fields.Char(
        string='ODBC Driver',
        config_parameter='topic_chatbot.mssql_driver',
        default='ODBC Driver 17 for SQL Server',
        help="Ví dụ: ODBC Driver 17 for SQL Server hoặc ODBC Driver 18 for SQL Server"
    )

    def action_test_mssql_connection(self):
        """Test connection to SQL Server database."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        host = self.topic_chatbot_mssql_host or params.get_param('topic_chatbot.mssql_host') or 'localhost'
        port = self.topic_chatbot_mssql_port or params.get_param('topic_chatbot.mssql_port') or '1433'
        db = self.topic_chatbot_mssql_db or params.get_param('topic_chatbot.mssql_db') or ''
        user = self.topic_chatbot_mssql_user or params.get_param('topic_chatbot.mssql_user') or ''
        password = self.topic_chatbot_mssql_password or params.get_param('topic_chatbot.mssql_password') or ''
        driver = self.topic_chatbot_mssql_driver or params.get_param('topic_chatbot.mssql_driver') or 'ODBC Driver 17 for SQL Server'

        if not db:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Cấu hình SQL Server',
                    'message': 'Vui lòng nhập tên Database Name cần kết nối.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        try:
            conn = None
            connector_used = ""

            # Thử pyodbc với danh sách Driver SQL Server có sẵn trên Windows
            try:
                import pyodbc
                if '\\' in host or '/' in host:
                    server_str = host.replace('/', '\\')
                else:
                    port_str = f",{port}" if port and str(port).strip() not in ("1433", "") else ""
                    server_str = f"{host}{port_str}"

                if user:
                    auth_str = f"UID={user};PWD={password};"
                else:
                    auth_str = "Trusted_Connection=yes;"

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
                        raise Exception(f"Thư viện pyodbc báo lỗi: {err_pyodbc}. Chưa cài đặt thư viện pymssql.")
                    else:
                        raise Exception("Chưa cài đặt thư viện Python 'pyodbc' hoặc 'pymssql' trên Server.")
                except Exception as e_pymssql:
                    raise Exception(f"Thất bại kết nối SQL Server: {str(e_pymssql)}")

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
                        'title': 'Kết nối SQL Server Thành Công!',
                        'message': f"Đã kết nối qua {connector_used}.\nPhiên bản SQL Server: {version_info[:80]}...",
                        'type': 'success',
                        'sticky': False,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi Kết Nối SQL Server',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }


    @api.model
    def _normalize_gemini_model(self, model):
        clean_model = (model or '').replace('models/', '').strip()
        valid_models = {value for value, _label in self._fields['topic_chatbot_gemini_model'].selection}
        clean_model = self.DEPRECATED_GEMINI_MODEL_MAP.get(clean_model, clean_model)
        return clean_model if clean_model in valid_models else 'gemini-3.6-flash'

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'topic_chatbot_gemini_model' in fields_list:
            params = self.env['ir.config_parameter'].sudo()
            raw_model = params.get_param('topic_chatbot.gemini_model')
            normalized_model = self._normalize_gemini_model(
                raw_model or res.get('topic_chatbot_gemini_model')
            )
            if raw_model != normalized_model:
                params.set_param('topic_chatbot.gemini_model', normalized_model)
            res['topic_chatbot_gemini_model'] = normalized_model
        if 'topic_chatbot_embedding_model' in fields_list:
            params = self.env['ir.config_parameter'].sudo()
            raw_embedding_model = params.get_param('topic_chatbot.embedding_model')
            if raw_embedding_model in ('text-embedding-004', 'embedding-001') or not raw_embedding_model:
                params.set_param('topic_chatbot.embedding_model', 'gemini-embedding-2')
                res['topic_chatbot_embedding_model'] = 'gemini-embedding-2'
        return res

    @api.model
    def get_values(self):
        res = super().get_values()
        params = self.env['ir.config_parameter'].sudo()
        raw_model = params.get_param('topic_chatbot.gemini_model')
        normalized_model = self._normalize_gemini_model(raw_model or res.get('topic_chatbot_gemini_model'))
        if raw_model != normalized_model:
            params.set_param('topic_chatbot.gemini_model', normalized_model)
        res['topic_chatbot_gemini_model'] = normalized_model

        raw_embedding_model = params.get_param('topic_chatbot.embedding_model')
        if raw_embedding_model in ('text-embedding-004', 'embedding-001') or not raw_embedding_model:
            params.set_param('topic_chatbot.embedding_model', 'gemini-embedding-2')
            res['topic_chatbot_embedding_model'] = 'gemini-embedding-2'
        return res

    def set_values(self):
        self.topic_chatbot_gemini_model = self._normalize_gemini_model(
            self.topic_chatbot_gemini_model
        )
        if self.topic_chatbot_embedding_model in ('text-embedding-004', 'embedding-001') or not self.topic_chatbot_embedding_model:
            self.topic_chatbot_embedding_model = 'gemini-embedding-2'
        return super().set_values()
