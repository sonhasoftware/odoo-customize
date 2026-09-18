import os
import requests
from odoo import api, fields, models
from . import crypto_utils

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

    topic_chatbot_llm_provider = fields.Selection([
        ('gemini', 'Google Gemini (Cloud)'),
        ('ollama', 'Ollama Server nội bộ (100% Offline / On-Premise)'),
    ], string='Chat LLM Provider',
        config_parameter='topic_chatbot.llm_provider',
        default='gemini',
        help="Chọn nhà cung cấp mô hình trí tuệ nhân tạo để sinh câu trả lời chat. Khi chọn Ollama Server, dữ liệu chạy 100% nội bộ."
    )
    topic_chatbot_ollama_chat_model = fields.Char(
        string='Ollama Chat Model',
        config_parameter='topic_chatbot.ollama_chat_model',
        default='qwen2.5:7b',
        help="Tên mô hình Chat LLM trên máy chủ Ollama (ví dụ: qwen2.5:7b hoặc qwen2.5:14b)."
    )
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
        help="Gemini text embedding model for Vector RAG Semantic Search (default: gemini-embedding-2)."
    )
    topic_chatbot_embedding_batch_size = fields.Integer(
        string='Embedding Batch Size',
        config_parameter='topic_chatbot.embedding_batch_size',
        default=50,
        help="Số lượng đoạn text gửi trong 1 request API batch (mặc định: 50, tối đa: 100)."
    )
    topic_chatbot_embedding_batch_delay_seconds = fields.Float(
        string='Delay giữa các batch (giây)',
        config_parameter='topic_chatbot.embedding_batch_delay_seconds',
        default=1.5,
        help="Thời gian nghỉ giữa các lần gọi API batch để bảo vệ quota (mặc định: 1.5 giây)."
    )
    topic_chatbot_embedding_provider = fields.Selection([
        ('gemini', 'Google Gemini (kèm Ollama Auto-Fallback khi hết quota)'),
        ('ollama', 'Ollama Local (100% Offline / Không phụ thuộc Gemini)'),
    ], string='Embedding Provider',
        config_parameter='topic_chatbot.embedding_provider',
        default='gemini',
        help="Chọn phương thức sinh vector embedding. Khi chọn Ollama Local, hệ thống hoàn toàn không gọi API Google Gemini."
    )
    topic_chatbot_ollama_url = fields.Char(
        string='Ollama Server URL',
        config_parameter='topic_chatbot.ollama_url',
        default='http://localhost:11434',
        help="Địa chỉ máy chủ Ollama (ví dụ: http://localhost:11434 hoặc IP server nội bộ)."
    )
    topic_chatbot_ollama_model = fields.Char(
        string='Ollama Embedding Model',
        config_parameter='topic_chatbot.ollama_model',
        default='bge-m3',
        help="Tên mô hình embedding trên Ollama. Khuyến nghị: bge-m3 (chuẩn 1024 chiều tối ưu tiếng Việt tương thích pgvector)."
    )

    # ── Cấu hình OCR & Nhận diện Hình ảnh trong tài liệu (Pilot v2) ───────────
    topic_chatbot_enable_image_ocr = fields.Boolean(
        string='Bật xử lý hình ảnh trong tài liệu',
        config_parameter='topic_chatbot.enable_image_ocr',
        default=True,
        help="Bật/Tắt tính năng bóc tách và OCR hình ảnh (sơ đồ, bảng biểu) trong file Word và PDF."
    )
    topic_chatbot_ocr_provider = fields.Selection([
        ('none', 'Tắt OCR (Chỉ đọc văn bản thuần)'),
        ('paddleocr', 'PaddleOCR + VietOCR nội bộ (CPU)'),
        ('gemini', 'Google Gemini Vision (Cloud)'),
    ], string='OCR Provider (Text / Bảng biểu)',
        config_parameter='topic_chatbot.ocr_provider',
        default='paddleocr',
        help="Phương thức OCR ký tự xác định cho ảnh bảng biểu, văn bản scan để tránh hallucination."
    )
    topic_chatbot_vision_provider = fields.Selection([
        ('none', 'Tắt Vision (Không phân tích sơ đồ)'),
        ('ollama', 'Ollama Vision nội bộ (Qwen2-VL / MiniCPM-V)'),
        ('gemini', 'Google Gemini Vision (Cloud)'),
    ], string='Vision Provider (Sơ đồ / Lưu đồ)',
        config_parameter='topic_chatbot.vision_provider',
        default='ollama',
        help="Phương thức VLM suy luận ngữ nghĩa cho sơ đồ quy trình, lưu đồ khối."
    )
    topic_chatbot_ollama_vision_model = fields.Char(
        string='Ollama Vision Model',
        config_parameter='topic_chatbot.ollama_vision_model',
        default='moondream',
        help="Tên model Vision trên máy chủ Ollama (ví dụ: moondream, llava-phi3, minicpm-v, llava)."
    )
    topic_chatbot_ocr_processing_mode = fields.Selection([
        ('sync', 'Đồng bộ khi tải/xử lý tài liệu'),
        ('queue', 'Hàng đợi tuần tự (Khuyến nghị Pilot CPU)'),
    ], string='Chế độ xử lý OCR',
        config_parameter='topic_chatbot.ocr_processing_mode',
        default='queue',
        help="Hàng đợi tuần tự xử lý 1 job/lần giúp bảo vệ CPU cho Chatbot LLM."
    )
    topic_chatbot_ocr_num_threads = fields.Integer(
        string='Số luồng CPU cho OCR/Vision',
        config_parameter='topic_chatbot.ocr_num_threads',
        default=lambda self: max(1, (os.cpu_count() or 4) - 2),
        help="Số luồng CPU cấp cho Ollama Vision / PaddleOCR (mặc định chừa 2 core cho Odoo và hệ điều hành)."
    )
    topic_chatbot_ocr_max_images = fields.Integer(
        string='Giới hạn số ảnh tối đa / tài liệu',
        config_parameter='topic_chatbot.ocr_max_images',
        default=15,
        help="Số lượng ảnh tối đa được OCR trong một tài liệu (tránh quá tải CPU)."
    )
    topic_chatbot_ocr_min_dimension = fields.Integer(
        string='Kích thước ảnh tối thiểu (px)',
        config_parameter='topic_chatbot.ocr_min_dimension',
        default=150,
        help="Bỏ qua các ảnh có chiều rộng hoặc chiều cao nhỏ hơn mức này (loại trừ icon, bullet, logo nhỏ)."
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
        # BUG #4 FIX: self.topic_chatbot_mssql_password đã được get_values() decrypt sẵn.
        # Fallback dùng params.get_param + decrypt để đảm bảo luôn lấy được plaintext.
        password = self.topic_chatbot_mssql_password or crypto_utils.decrypt_value(
            self.env, params.get_param('topic_chatbot.mssql_password') or ''
        )
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

    def action_test_ollama_connection(self):
        """Test connection to Ollama Local Server and verify embedding model."""
        self.ensure_one()
        from ..services import embedding_service
        params = self.env['ir.config_parameter'].sudo()
        url = self.topic_chatbot_ollama_url or params.get_param('topic_chatbot.ollama_url') or 'http://localhost:11434'
        model = self.topic_chatbot_ollama_model or params.get_param('topic_chatbot.ollama_model') or 'bge-m3'
        
        res = embedding_service.test_ollama_connection(url, model)
        if res.get('success'):
            if res.get('model_found'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Kết nối Ollama Thành công',
                        'message': res['message'],
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Cảnh báo Model Ollama',
                        'message': res['message'],
                        'type': 'warning',
                        'sticky': True,
                    }
                }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Kết nối Ollama Thất bại',
                    'message': res['message'],
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_test_ollama_vision_connection(self):
        """Test connection to Ollama server and verify if Vision model is available."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        ollama_url = (self.topic_chatbot_ollama_url or params.get_param('topic_chatbot.ollama_url') or 'http://localhost:11434').rstrip('/')
        model_name = self.topic_chatbot_ollama_vision_model or params.get_param('topic_chatbot.ollama_vision_model') or 'qwen2-vl:2b'

        try:
            res = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if res.status_code == 200:
                models_data = res.json().get('models', [])
                installed_names = [m.get('name', '') for m in models_data]
                is_installed = any(model_name in name or name.startswith(model_name) for name in installed_names)
                if is_installed:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Kết nối Ollama Vision Thành Công',
                            'message': f"Máy chủ Ollama tại '{ollama_url}' đang hoạt động tốt. Model Vision '{model_name}' đã sẵn sàng!",
                            'type': 'success',
                            'sticky': False,
                        }
                    }
                else:
                    installed_str = ', '.join([n.split(':')[0] for n in installed_names[:6]])
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Cảnh báo: Chưa cài đặt Model Vision',
                            'message': f"Kết nối Ollama OK, nhưng model '{model_name}' chưa được tải về. Vui lòng chạy lệnh: `ollama run {model_name}` trên server. Các model hiện có: {installed_str}",
                            'type': 'warning',
                            'sticky': True,
                        }
                    }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Lỗi phản hồi Ollama',
                        'message': f"Ollama Server trả về HTTP {res.status_code}: {res.text[:200]}",
                        'type': 'danger',
                        'sticky': True,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Không thể kết nối Ollama',
                    'message': f"Không thể kết nối tới '{ollama_url}': {str(e)}",
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def action_test_paddleocr_connection(self):
        """Test if PaddleOCR and VietOCR libraries are ready."""
        self.ensure_one()
        try:
            from ..services import ocr_service
            engine = ocr_service.get_paddle_ocr_engine()
            if engine:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'PaddleOCR Khả Dụng',
                        'message': "Thư viện PaddleOCR đã được cài đặt và khởi tạo thành công trên CPU!",
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                params = self.env['ir.config_parameter'].sudo()
                gemini_key = params.get_param('topic_chatbot.gemini_api_key')
                fallback_info = " Gemini API Key đã cấu hình -> Hệ thống sẽ tự động fallback sang Gemini Cloud OCR." if gemini_key else " Chưa cấu hình Gemini API Key -> OCR có thể bị gián đoạn."
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'PaddleOCR Chưa Cài Đặt',
                        'message': f"Môi trường Python chưa cài đặt PaddleOCR.{fallback_info} (Để dùng local: pip install paddlepaddle paddleocr).",
                        'type': 'warning',
                        'sticky': True,
                    }
                }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Lỗi kiểm tra PaddleOCR',
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

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

        # BUG #4 FIX: Decrypt password trước khi trả về UI.
        # Giá trị trong DB là 'tc_enc:...' — cần decrypt để field hiển thị đúng.
        # Field dùng password="True" nên không lộ ra ngoài trình duyệt dưới dạng text thuần.
        raw_pw = res.get('topic_chatbot_mssql_password', '')
        res['topic_chatbot_mssql_password'] = crypto_utils.decrypt_value(self.env, raw_pw)
        return res

    def set_values(self):
        # BUG #4 FIX: Encrypt password TRƯỚC khi super().set_values() lưu vào ir.config_parameter.
        # self.topic_chatbot_mssql_password lúc này là plaintext (người dùng vừa nhập hoặc
        # đã được get_values() decrypt và điền lại vào form).
        if self.topic_chatbot_mssql_password and not crypto_utils.is_encrypted(self.topic_chatbot_mssql_password):
            self.topic_chatbot_mssql_password = crypto_utils.encrypt_value(
                self.env, self.topic_chatbot_mssql_password
            )
        self.topic_chatbot_gemini_model = self._normalize_gemini_model(
            self.topic_chatbot_gemini_model
        )
        if self.topic_chatbot_embedding_model in ('text-embedding-004', 'embedding-001') or not self.topic_chatbot_embedding_model:
            self.topic_chatbot_embedding_model = 'gemini-embedding-2'
        return super().set_values()

