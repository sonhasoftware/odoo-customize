# -*- coding: utf-8 -*-
import json
import logging
import re
import requests
from datetime import datetime, timedelta
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class TopicChatbotController(http.Controller):

    @http.route('/topic_chatbot/get_topics', type='json', auth='user')
    def get_topics(self):
        """Fetch all topics the user has access to."""
        topics = request.env['topic_chatbot.topic'].search([])
        return [{
            'id': t.id,
            'name': t.name,
            'description': t.description or '',
            'is_public': t.is_public,
            'is_db_query': t.is_db_query,
            'is_mssql_query': t.is_mssql_query,
            'owner': t.create_uid.name
        } for t in topics]

    @http.route('/topic_chatbot/get_conversations', type='json', auth='user')
    def get_conversations(self, topic_id):
        """Fetch all conversations for a specific topic of the current user."""
        try:
            topic_id_int = int(topic_id)
        except (ValueError, TypeError):
            return []
        # Check topic access (record rules will restrict search)
        topic = request.env['topic_chatbot.topic'].search([('id', '=', topic_id_int)])
        if not topic:
            return []

        conversations = request.env['topic_chatbot.conversation'].search([
            ('topic_id', '=', topic.id),
            ('user_id', '=', request.env.uid)
        ])
        return [{
            'id': c.id,
            'name': c.name,
            'topic_id': c.topic_id.id,
            'create_date': c.create_date
        } for c in conversations]

    @http.route('/topic_chatbot/get_messages', type='json', auth='user')
    def get_messages(self, conversation_id):
        """Fetch messages in a conversation."""
        try:
            conversation_id_int = int(conversation_id)
        except (ValueError, TypeError):
            return []
        # Security check: User must own the conversation
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return []

        # Check topic access
        topic = request.env['topic_chatbot.topic'].search([('id', '=', conversation.topic_id.id)])
        if not topic:
            return []

        messages = request.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation.id)
        ], order='create_date asc, id asc')
        return [{
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'create_date': m.create_date
        } for m in messages]

    @http.route('/topic_chatbot/create_conversation', type='json', auth='user')
    def create_conversation(self, topic_id):
        """Create a new conversation for a topic."""
        try:
            topic_id_int = int(topic_id)
        except (ValueError, TypeError):
            return {'error': 'Topic not found.'}
        topic = request.env['topic_chatbot.topic'].browse(topic_id_int)
        if not topic.exists():
            return {'error': 'Topic not found.'}

        # Verify access
        try:
            topic.check_access_rule('read')
        except Exception:
            return {'error': 'Access Denied.'}

        conversation = request.env['topic_chatbot.conversation'].create({
            'name': 'New Chat',
            'topic_id': topic.id,
            'user_id': request.env.uid
        })
        return {
            'id': conversation.id,
            'name': conversation.name,
            'topic_id': conversation.topic_id.id
        }

    @http.route('/topic_chatbot/delete_conversation', type='json', auth='user')
    def delete_conversation(self, conversation_id):
        """Delete a conversation."""
        try:
            conversation_id_int = int(conversation_id)
        except (ValueError, TypeError):
            return {'error': 'Conversation not found or access denied.'}
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if conversation:
            conversation.unlink()
            return {'success': True}
        return {'error': 'Conversation not found or access denied.'}

    def _build_system_instruction(self, context_str, is_db_query=False, is_mssql_query=False, mssql_tables=""):
        db_task_instruction = ""
        capability_items = []

        if is_mssql_query:
            table_info = f" Các bảng/view có sẵn trong CSDL SQL Server: {mssql_tables}." if mssql_tables else ""
            db_task_instruction += (
                f"1. QUYỀN TRUY VẤN SQL SERVER: Chủ đề này ĐÃ BẬT TÍNH NĂNG KẾT NỐI VÀ TRA CỨU CSDL MICROSOFT SQL SERVER.{table_info}\n"
                "Khi người dùng hỏi về bất kỳ dữ liệu thực tế nào (như danh sách sản phẩm, giá bán, bồn nước, tồn kho, danh mục, v.v.), "
                "bạn BẮT BUỘC KHÔNG ĐƯỢC TỪ CHỐI, mà BẮT BUỘC PHẢI GỌI CÔNG CỤ 'query_sql_server_data' với câu lệnh SELECT T-SQL để lấy dữ liệu thực tế từ SQL Server. "
                "Sau khi nhận kết quả dữ liệu từ công cụ, hãy trình bày thành bảng Markdown đẹp mắt cho người dùng.\n"
            )
            capability_items.append(f"Tra cứu dữ liệu thực tế từ CSDL SQL Server{table_info}")

        if is_db_query:
            db_task_instruction += (
                "2. ĐỐI VỚI DỮ LIỆU ODOO: Bạn được cấp công cụ 'query_odoo_data' để tra cứu Nhân viên, Phòng ban, KPI trên hệ thống Odoo.\n"
            )
            capability_items.append("Tra cứu dữ liệu Odoo (Nhân viên, Phòng ban, KPI)")

        capability_items.append("Trả lời dựa trên tài liệu nội bộ được tải lên")
        capability_items.append("Hỗ trợ tóm tắt, giải thích và xử lý công việc thông thường")

        capability_str = "; ".join([f"({idx+1}) {item}" for idx, item in enumerate(capability_items)])
        capability_instruction = (
            f"3. KHẢ NĂNG HỖ TRỢ CỦA BẠN: Nếu người dùng hỏi bạn có thể làm được gì, hãy nêu rõ: {capability_str}.\n"
        )

        return (
            "Bạn là trợ lý AI nội bộ hỗ trợ người dùng tra cứu dữ liệu và tài liệu thuộc chủ đề đang chọn.\n"
            "NHIỆM VỤ VÀ NGUYÊN TẮC HOẠT ĐỘNG CỦA BẠN:\n"
            f"{db_task_instruction}"
            f"{capability_instruction}"
            "4. ĐỐI VỚI TÀI LIỆU RAG: Nếu người dùng hỏi về quy trình, hướng dẫn, chính sách, hãy bám sát nội dung tài liệu tham khảo.\n"
            "5. BẢO MẬT HỆ THỐNG: BẮT BUỘC KHÔNG BAO GIỜ tiết lộ tên bảng (table), tên cột (column), nguyên văn câu lệnh SQL, hoặc cấu trúc CSDL nội bộ cho người dùng. Nếu người dùng hỏi dữ liệu được lấy từ đâu, chỉ trả lời chung chung là 'từ hệ thống CSDL của công ty'.\n"
            "6. PHONG CÁCH TRẢ LỜI: Viết bằng tiếng Việt tự nhiên, lịch sự, thực dụng. Ưu tiên câu trả lời trình bày dạng bảng Markdown rõ ràng.\n\n"
            "NỘI DUNG TÀI LIỆU THAM KHẢO (NẾU CÓ):\n"
            f"<TAI_LIEU_THAM_KHAO>\n{context_str}\n</TAI_LIEU_THAM_KHAO>"
        )

    def _sanitize_technical_terms(self, text):
        """Sanitize response text to replace technical database/model/field terms with business terms."""
        if not text:
            return text

        replacements = {
            r'\bquery_odoo_data\b': 'hệ thống tra cứu dữ liệu Odoo',
            r'\bcác model\b': 'các loại dữ liệu',
            r'\bmodel\b': 'dữ liệu',
            r'\bmodels\b': 'dữ liệu',
            r'\bhr\.employee\b': 'thông tin nhân viên',
            r'\bhr\.department\b': 'thông tin phòng ban',
            r'\bsonha\.kpi\.result\.month\b': 'kết quả KPI tháng',
            r'\breport\.kpi\.month\b': 'đánh giá KPI lãnh đạo',
            r'\bsonha\.kpi\.year\b': 'KPI năm',
            r'\bdepartment_id\b': 'phòng ban',
            r'\bemployee_id\b': 'nhân viên',
            r'\bcomplete_name\b': 'tên đầy đủ',
            r'\bjob_title\b': 'chức danh',
            r'\bwork_email\b': 'email công việc',
            r'\bwork_phone\b': 'số điện thoại',
            r'\bmanager_id\b': 'quản lý',
            r'\bparent_id\b': 'đơn vị cấp trên',
            r'\bcreate_uid\b': 'người tạo',
            r'\bcreate_date\b': 'ngày tạo',
            r'\bwrite_date\b': 'ngày cập nhật',
        }

        sanitized_text = text
        for pattern, replacement in replacements.items():
            sanitized_text = re.sub(pattern, replacement, sanitized_text, flags=re.IGNORECASE)
        return sanitized_text

    def _execute_odoo_query(self, model, domain=None, fields=None, env=None):
        """Execute a safe, read-only Odoo search_read query using the given or current user's environment."""
        if env is None:
            try:
                env = request.env
            except Exception:
                return {'error': 'Không thể khởi tạo môi trường truy vấn Odoo.'}

        safe_models = [
            'hr.employee',
            'hr.department',
            'sonha.kpi.result.month',
            'report.kpi.month',
            'sonha.kpi.year'
        ]

        if model not in safe_models:
            return {'error': 'Loại dữ liệu này không thuộc phạm vi truy vấn được phép hoặc bị hạn chế vì lý do bảo mật.'}

        if model not in env:
            return {'error': 'Loại dữ liệu yêu cầu không tồn tại trên hệ thống.'}

        model_obj = env[model]
        valid_model_fields = set(model_obj._fields.keys())

        # Lọc bỏ các tên field không tồn tại do AI tự suy đoán
        clean_fields = []
        if fields and isinstance(fields, list):
            for f in fields:
                if isinstance(f, str) and f in valid_model_fields:
                    clean_fields.append(f)

        # Nếu mảng fields rỗng hoặc AI truyền sai toàn bộ fields, gán mảng field mặc định an toàn
        if not clean_fields:
            default_field_map = {
                'hr.department': ['name', 'complete_name', 'manager_id', 'parent_id'],
                'hr.employee': ['name', 'work_email', 'work_phone', 'job_title', 'department_id'],
                'sonha.kpi.result.month': ['name', 'employee_id', 'department_id', 'score', 'month', 'year', 'state'],
                'report.kpi.month': ['name', 'department_id', 'score', 'month', 'year', 'state'],
                'sonha.kpi.year': ['name', 'employee_id', 'department_id', 'score', 'year', 'state'],
            }
            clean_fields = [f for f in default_field_map.get(model, ['name', 'display_name']) if f in valid_model_fields]

        # Chuyển đổi domain từ chuỗi JSON sang list nếu cần thiết
        domain_list = []
        if domain:
            if isinstance(domain, str):
                try:
                    from odoo.tools.safe_eval import safe_eval
                    domain_list = safe_eval(domain)
                except Exception as e:
                    return {'error': f"Không thể phân tích cú pháp domain: {str(e)}"}
            elif isinstance(domain, list):
                domain_list = domain
        else:
            domain_list = []

        # Ánh xạ tên phòng ban/nhân viên nếu AI truyền chuỗi text thay vì ID
        clean_domain = []
        for term in domain_list:
            if isinstance(term, list) and len(term) == 3:
                field, op, val = term
                if field == 'department_id' and isinstance(val, str):
                    # Bóc tách loại bỏ mã prefix số (ví dụ '3949 - Phòng Quản lý chất lượng' -> 'Phòng Quản lý chất lượng')
                    clean_v = re.sub(r'^[0-9\s\-_]+', '', val).strip() or val
                    short_v = clean_v.replace('phòng', '').replace('Phòng', '').replace('ban', '').replace('Ban', '').strip()
                    dept = env['hr.department'].search([
                        '|', '|', '|',
                        ('name', 'ilike', val),
                        ('complete_name', 'ilike', val),
                        ('name', 'ilike', clean_v),
                        ('complete_name', 'ilike', clean_v)
                    ], limit=1)
                    if not dept and short_v:
                        dept = env['hr.department'].search([
                            '|',
                            ('name', 'ilike', short_v),
                            ('complete_name', 'ilike', short_v)
                        ], limit=1)
                    if dept:
                        clean_domain.append([field, '=', dept.id])
                        continue
                    else:
                        return {'error': f"Không tìm thấy phòng ban nào khớp với tên '{val}'."}
                elif field == 'employee_id' and isinstance(val, str):
                    clean_v = re.sub(r'^[0-9\s\-_]+', '', val).strip() or val
                    emp = env['hr.employee'].search([
                        '|',
                        ('name', 'ilike', val),
                        ('name', 'ilike', clean_v)
                    ], limit=1)
                    if emp:
                        clean_domain.append([field, '=', emp.id])
                        continue
                    else:
                        return {'error': f"Không tìm thấy nhân viên nào có tên '{val}'."}
            clean_domain.append(term)

        try:
            records = model_obj.search_read(clean_domain, clean_fields, limit=80)
            is_truncated = (len(records) == 80)

            cleaned_records = []
            for rec in records:
                clean_rec = {}
                for k, v in rec.items():
                    if isinstance(v, tuple) and len(v) == 2:
                        clean_rec[k] = v[1]
                    else:
                        clean_rec[k] = v
                cleaned_records.append(clean_rec)

            if 'name' in clean_fields:
                filtered_records = []
                for rec in cleaned_records:
                    name_val = rec.get('name')
                    if name_val is None:
                        continue
                    name_str = str(name_val).strip()
                    if not name_str:
                        continue
                    if re.match(r'^[0-9\s]+$', name_str):
                        continue
                    filtered_records.append(rec)
                cleaned_records = filtered_records

            if is_truncated:
                return {
                    'data': cleaned_records,
                    'truncated': True,
                    'notice': 'Kết quả có thể chưa đầy đủ do giới hạn số bản ghi mỗi lần truy vấn. Vui lòng thu hẹp phạm vi câu hỏi để có kết quả chính xác hơn.'
                }
            return cleaned_records
        except Exception as e:
            from odoo.exceptions import AccessError
            if isinstance(e, AccessError):
                return {'error': 'You do not have permission to access this data on the Odoo system.'}
            safe_err = str(e).encode('ascii', 'backslashreplace').decode('ascii')
            _logger.error("Odoo ORM Query Error (%s): %s", model, safe_err)
            return {'error': f'Error querying data from Odoo: {str(e)}'}

    def _execute_mssql_query(self, sql_query, topic=None, env=None):
        """Execute a safe, read-only T-SQL SELECT query on Microsoft SQL Server."""
        if env is None:
            try:
                env = request.env
            except Exception:
                return {'error': 'Không thể khởi tạo môi trường truy vấn Odoo.'}

        params = env['ir.config_parameter'].sudo()
        mssql_enabled = params.get_param('topic_chatbot.mssql_enabled', 'False').lower() in ('true', '1')
        mssql_db = params.get_param('topic_chatbot.mssql_db') or ''
        if not mssql_enabled and not mssql_db:
            return {'error': 'Tính năng kết nối SQL Server chưa được bật trong Cấu hình Chatbot.'}

        host = params.get_param('topic_chatbot.mssql_host') or 'localhost'
        port = params.get_param('topic_chatbot.mssql_port') or '1433'
        db = params.get_param('topic_chatbot.mssql_db') or ''
        user = params.get_param('topic_chatbot.mssql_user') or ''
        password = params.get_param('topic_chatbot.mssql_password') or ''
        driver = params.get_param('topic_chatbot.mssql_driver') or 'ODBC Driver 17 for SQL Server'

        if not db:
            return {'error': 'Cấu hình thông tin kết nối SQL Server (Database Name) chưa đầy đủ.'}

        if not sql_query or not isinstance(sql_query, str):
            return {'error': 'Câu lệnh SQL không hợp lệ.'}

        # 1. Security Checks (Strict READ ONLY ENFORCEMENT)
        clean_query = sql_query.strip()
        clean_query_no_comments = re.sub(r'--.*$', '', clean_query, flags=re.MULTILINE)
        clean_query_no_comments = re.sub(r'/\*.*?\*/', '', clean_query_no_comments, flags=re.DOTALL).strip()

        if ';' in clean_query_no_comments:
            return {'error': 'Vì lý do an toàn, hệ thống không cho phép chạy nhiều câu lệnh SQL cùng lúc (chứa dấu ;).'}

        upper_query = clean_query_no_comments.upper()
        if not (upper_query.startswith('SELECT') or upper_query.startswith('WITH')):
            return {'error': 'Vì lý do an toàn bảo mật, hệ thống chỉ cho phép thực thi câu lệnh đọc dữ liệu SELECT.'}

        forbidden_keywords = [
            r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b', r'\bDROP\b', r'\bALTER\b',
            r'\bCREATE\b', r'\bTRUNCATE\b', r'\bEXEC\b', r'\bEXECUTE\b', r'\bGRANT\b',
            r'\bREVOKE\b', r'\bMERGE\b', r'\bINTO\b', r'\bSP_\b', r'\bXP_\b'
        ]
        for pattern in forbidden_keywords:
            if re.search(pattern, upper_query):
                kw_clean = pattern.replace(r'\b', '')
                return {'error': f'Câu lệnh SQL chứa từ khóa bị cấm vì lý do bảo mật: {kw_clean}'}

        if topic and topic.mssql_allowed_tables:
            allowed_tables = set()
            for table in re.split(r'[\n,;]+', topic.mssql_allowed_tables or ''):
                table_name = table.strip().split()[0].strip('[]')
                if not table_name:
                    continue
                normalized = table_name.replace('[', '').replace(']', '').replace(' ', '').lower()
                allowed_tables.add(normalized)
                allowed_tables.add(normalized.split('.')[-1])

            table_refs = re.findall(
                r'\b(?:FROM|JOIN)\s+((?:\[[^\]]+\]|\w+)(?:\s*\.\s*(?:\[[^\]]+\]|\w+)){0,2})',
                clean_query_no_comments,
                flags=re.IGNORECASE
            )
            for table_ref in table_refs:
                normalized_ref = table_ref.replace('[', '').replace(']', '').replace(' ', '').lower()
                if normalized_ref not in allowed_tables and normalized_ref.split('.')[-1] not in allowed_tables:
                    return {
                        'error': (
                            'Bang/view trong cau lenh SQL khong nam trong danh sach duoc phep '
                            f'cua chu de: {table_ref}.'
                        )
                    }

        # Auto-inject TOP 100 if query has no TOP clause
        if 'SELECT' in upper_query and not re.search(r'\bSELECT\s+(DISTINCT\s+)?TOP\b', upper_query):
            clean_query_no_comments = re.sub(
                r'^(\s*SELECT)(\s+DISTINCT)?\s+',
                r'\1\2 TOP 100 ',
                clean_query_no_comments,
                count=1,
                flags=re.IGNORECASE
            )

        # 2. Connect & Execute
        conn = None
        try:
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

                drivers_to_try = []
                try:
                    installed = pyodbc.drivers()
                    _logger.info("Installed ODBC drivers: %s", installed)
                    # Ưu tiên: ODBC Driver 18 > 17 > SQL Server (bỏ Native Client dễ lỗi registry)
                    priority = []
                    others = []
                    for d in installed:
                        dl = d.lower()
                        if 'sql server' not in dl:
                            continue
                        if 'native client' in dl:
                            continue  # Bỏ qua Native Client (hay gặp lỗi registry)
                        if 'odbc driver' in dl:
                            priority.append(d)
                        else:
                            others.append(d)
                    # ODBC Driver số cao hơn lên trước
                    drivers_to_try = sorted(priority, reverse=True) + others
                except Exception:
                    pass

                # Fallback: thêm driver từ cấu hình nếu chưa có
                if driver and driver not in drivers_to_try:
                    drivers_to_try.append(driver)
                # Fallback cuối: driver built-in
                if 'SQL Server' not in drivers_to_try:
                    drivers_to_try.append('SQL Server')

                _logger.info("MSSQL drivers_to_try: %s", drivers_to_try)
                for drv in drivers_to_try:
                    try:
                        conn_str = (
                            f"DRIVER={{{drv}}};SERVER={server_str};DATABASE={db};"
                            f"{auth_str}TrustServerCertificate=yes;Connection Timeout=10;"
                        )
                        conn = pyodbc.connect(conn_str, timeout=15)
                        _logger.info("MSSQL connected successfully using driver: %s", drv)
                        break
                    except Exception as ex_drv:
                        _logger.warning("pyodbc driver %s failed: %s", drv, str(ex_drv))
            except ImportError:
                pass

            if not conn:
                try:
                    import pymssql
                    port_int = int(port) if port else 1433
                    conn = pymssql.connect(
                        server=host, port=port_int, user=user, password=password, database=db, login_timeout=15
                    )
                except ImportError:
                    return {'error': 'Chưa cài đặt thư viện kết nối SQL Server (pyodbc hoặc pymssql) trên Server Odoo.'}
                except Exception as e_pymssql:
                    return {'error': f'Không thể kết nối SQL Server: {str(e_pymssql)}'}

            cursor = conn.cursor()
            cursor.execute(clean_query_no_comments)

            if not cursor.description:
                conn.close()
                return {'error': 'Câu lệnh không trả về dữ liệu.'}

            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchmany(100)
            conn.close()

            results = []
            from datetime import datetime as dt, date as dt_date
            import decimal
            for row in rows:
                item = {}
                for idx, col in enumerate(columns):
                    val = row[idx]
                    if isinstance(val, (dt, dt_date)):
                        val = val.isoformat()
                    elif isinstance(val, bytes):
                        val = '<binary data>'
                    elif isinstance(val, decimal.Decimal):
                        val = float(val)
                    item[col] = val
                results.append(item)

            return {
                'data': results,
                'count': len(results),
                'columns': columns,
                'notice': 'Dữ liệu được truy vấn an toàn từ SQL Server (tối đa 100 dòng).'
            }

        except Exception as e:
            safe_query = clean_query_no_comments.encode('ascii', 'backslashreplace').decode('ascii')
            safe_err = str(e).encode('ascii', 'backslashreplace').decode('ascii')
            _logger.error("MSSQL Query Error [%s]: %s", safe_query, safe_err)
            return {'error': f'Lỗi thực thi truy vấn SQL Server: {str(e)}'}

    # =========================================================
    # Rate Limiting
    # =========================================================
    RATE_LIMIT_MAX_MESSAGES = 5
    RATE_LIMIT_WINDOW_SECONDS = 60

    def _check_rate_limit(self, env, user_id):
        """Check if user has exceeded the rate limit.
        Returns True if rate limit exceeded, False otherwise.
        Args:
            env: Odoo environment (request.env or self.env in tests)
            user_id: ID of the user to check
        """
        cutoff = datetime.utcnow() - timedelta(seconds=self.RATE_LIMIT_WINDOW_SECONDS)
        recent_count = env['topic_chatbot.message'].sudo().search_count([
            ('conversation_id.user_id', '=', user_id),
            ('role', '=', 'user'),
            ('create_date', '>=', cutoff),
        ])
        return recent_count >= self.RATE_LIMIT_MAX_MESSAGES

    def _redact_api_key(self, value, api_key):
        if value and api_key:
            return str(value).replace(api_key, "REDACTED")
        return value

    def _extract_gemini_error(self, response, api_key=None):
        """Return sanitized Gemini error details for logging and user messaging."""
        details = {
            'status_code': getattr(response, 'status_code', None),
            'status': '',
            'message': '',
            'raw': '',
        }
        try:
            data = response.json()
            error = data.get('error', {}) if isinstance(data, dict) else {}
            details['status'] = error.get('status') or ''
            details['message'] = error.get('message') or ''
        except Exception:
            details['raw'] = getattr(response, 'text', '') or ''

        for key in ('status', 'message', 'raw'):
            details[key] = self._redact_api_key(details[key], api_key)
        return details

    def _gemini_user_error_message(self, status_code=None, error_status='', error_message=''):
        """Map Gemini/API transport failures to an actionable user-facing message."""
        normalized_status = (error_status or '').upper()
        normalized_message = (error_message or '').lower()

        if status_code == 429 or normalized_status == 'RESOURCE_EXHAUSTED':
            return (
                "Gemini API đang bị giới hạn lượt gọi/quota (429). "
                "Vui lòng chờ một lát rồi thử lại, hoặc kiểm tra quota và billing của API key."
            )
        if status_code in (401, 403) or normalized_status in ('UNAUTHENTICATED', 'PERMISSION_DENIED'):
            return (
                "Gemini API key không hợp lệ, hết quyền truy cập, hoặc chưa bật quyền cho model đang dùng. "
                "Vui lòng kiểm tra lại API key trong Cấu hình."
            )
        if status_code == 404 or normalized_status == 'NOT_FOUND':
            return (
                "Model Gemini đang cấu hình không tồn tại hoặc không còn được hỗ trợ. "
                "Vui lòng chọn lại model trong Cấu hình chatbot."
            )
        if status_code == 400 or normalized_status == 'INVALID_ARGUMENT':
            if 'api key' in normalized_message:
                return "Gemini API key không hợp lệ. Vui lòng kiểm tra lại API key trong Cấu hình."
            return (
                "Gemini từ chối yêu cầu do dữ liệu gửi lên chưa hợp lệ. "
                "Vui lòng thử lại với câu hỏi ngắn hơn hoặc kiểm tra cấu hình chatbot."
            )
        if status_code and status_code >= 500:
            return "Gemini API đang gặp lỗi tạm thời. Vui lòng thử lại sau ít phút."
        return "Đã xảy ra lỗi khi kết nối tới Gemini API. Vui lòng thử lại sau."

    @http.route('/topic_chatbot/ask', type='json', auth='user')
    def ask(self, conversation_id, message):
        """Send message to Gemini API with RAG context and Odoo Tools."""
        try:
            conversation_id_int = int(conversation_id)
        except (ValueError, TypeError):
            return {'error': 'Conversation not found or access denied.'}
        # 1. Fetch conversation & check ownership
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return {'error': 'Conversation not found or access denied.'}

        # Rate limiting: Chặn spam gọi API
        if self._check_rate_limit(request.env, request.env.uid):
            return {'error': f'Bạn đã gửi quá {self.RATE_LIMIT_MAX_MESSAGES} câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại.'}

        # Chặn gửi câu hỏi mới khi câu trước đang xử lý
        if conversation.is_processing:
            return {'error': 'Vui lòng chờ câu trả lời trước hoàn tất trước khi gửi câu hỏi mới.'}
        conversation.sudo().write({'is_processing': True})

        # Verify access to the topic
        topic = request.env['topic_chatbot.topic'].sudo().browse(conversation.topic_id.id)
        if not topic.exists():
            conversation.sudo().write({'is_processing': False})
            return {'error': 'Truy cập vào chủ đề này bị từ chối hoặc không khả dụng.'}

        is_mssql_active = bool(
            topic.is_mssql_query or 
            (topic.mssql_allowed_tables and topic.mssql_allowed_tables.strip()) or 
            ('sql' in (topic.name or '').lower())
        )

        _logger.info("Chatbot Ask Endpoint - Topic ID: %s | Name: '%s' | is_mssql_query: %s | is_mssql_active: %s",
                     topic.id, topic.name, topic.is_mssql_query, is_mssql_active)

        bot_reply_saved = False
        try:
            # 2. Save user message
            request.env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'user',
                'content': message
            })

            # 3. Retrieve relevant chunks (RAG)
            topic_id = conversation.topic_id.id
            chunks = self._retrieve_context(topic_id, message)

            # 4. Construct System Instruction
            context_str = "\n\n".join([
                (
                    f"--- Nguồn: {chunk['document_name']}, đoạn {chunk['sequence']} ---\n"
                    f"{chunk['content']}"
                )
                for chunk in chunks
            ])

            system_instruction = self._build_system_instruction(
                context_str, 
                is_db_query=topic.is_db_query,
                is_mssql_query=is_mssql_active,
                mssql_tables=topic.mssql_allowed_tables or ""
            )

            # 5. Fetch API Credentials
            params = request.env['ir.config_parameter'].sudo()
            api_key = params.get_param('topic_chatbot.gemini_api_key')
            model = (params.get_param('topic_chatbot.gemini_model') or 'gemini-3.6-flash').replace('models/', '').strip()
            deprecated_model_map = {
                'gemini-1.5-flash': 'gemini-3.5-flash-lite',
                'gemini-1.5-pro': 'gemini-3.1-pro-preview',
                'gemini-2.0-flash': 'gemini-3.6-flash',
                'gemini-2.0-flash-001': 'gemini-3.6-flash',
                'gemini-2.0-flash-lite': 'gemini-3.5-flash-lite',
                'gemini-2.0-flash-lite-001': 'gemini-3.5-flash-lite',
            }
            model = deprecated_model_map.get(model, model)

            if not api_key:
                error_msg = "Chưa cấu hình Gemini API Key. Vui lòng liên hệ Administrator để thiết lập trong Cấu hình."
                request.env['topic_chatbot.message'].create({
                    'conversation_id': conversation.id,
                    'role': 'model',
                    'content': error_msg
                })
                bot_reply_saved = True
                return {'response': error_msg}

            # 6. Format chat history for Gemini API (Limit by total characters instead of just message count)
            db_messages = request.env['topic_chatbot.message'].search([
                ('conversation_id', '=', conversation.id)
            ], order='create_date desc')

            contents = []
            total_chars = 0
            MAX_CHARS = 30000
            
            for m in db_messages:
                # Clean up excessive consecutive spaces to avoid prompt contamination
                cleaned_content = re.sub(r' {2,}', ' ', m.content or '')
                
                # Check character limit
                if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                    break

                total_chars += len(cleaned_content)
                contents.insert(0, {
                    'role': 'user' if m.role == 'user' else 'model',
                    'parts': [{'text': cleaned_content}]
                })

            # 7. Request to Gemini API with Tool Loop
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            headers = {'Content-Type': 'application/json'}
            payload = {
                'contents': contents,
                'systemInstruction': {
                    'parts': [{'text': system_instruction}]
                },
                'generationConfig': {
                    'maxOutputTokens': 8192
                }
            }

            tools_list = []
            if topic.is_db_query:
                tools_list.append({
                    'name': 'query_odoo_data',
                    'description': (
                        'Truy vấn đọc dữ liệu (Read-only) an toàn từ database Odoo '
                        'để tìm thông tin liên quan đến các dữ liệu nghiệp vụ: Nhân viên, '
                        'Phòng ban, Kết quả KPI tháng, Đánh giá KPI của lãnh đạo, KPI năm.\n'
                        'CHỈ sử dụng công cụ này khi người dùng hỏi các câu hỏi thực tế về dữ liệu '
                        'hệ thống Odoo (như KPI của một ai đó, xếp loại phòng ban, danh sách nhân viên, v.v.).'
                    ),
                    'parameters': {
                        'type': 'OBJECT',
                        'properties': {
                            'model': {
                                'type': 'STRING',
                                'description': (
                                    'Tên model Odoo cần truy vấn. Chỉ chấp nhận các giá trị: '
                                    '"hr.employee", "hr.department", "sonha.kpi.result.month", '
                                    '"report.kpi.month", "sonha.kpi.year".'
                                )
                            },
                            'domain': {
                                'type': 'STRING',
                                'description': 'Mảng các điều kiện lọc dạng Odoo Domain (chuỗi JSON), ví dụ: "[[\"department_id\", \"=\", 5], [\"year\", \"=\", 2025]]".'
                            },
                            'fields': {
                                'type': 'ARRAY',
                                'items': {
                                    'type': 'STRING'
                                },
                                'description': 'Mảng chứa tên các trường thông tin cần lấy dữ liệu (ví dụ: ["name", "score", "state"])'
                            }
                        },
                        'required': ['model', 'fields']
                    }
                })

            if is_mssql_active:
                allowed_info = f" Danh sách bảng/view được phép: {topic.mssql_allowed_tables}." if topic.mssql_allowed_tables else ""
                tools_list.append({
                    'name': 'query_sql_server_data',
                    'description': (
                        'Truy vấn đọc dữ liệu (Read-only) an toàn từ CSDL Microsoft SQL Server bằng câu lệnh T-SQL SELECT.\n'
                        f'{allowed_info}\n'
                        'CHỈ sử dụng công cụ này khi người dùng hỏi các câu hỏi về dữ liệu thực tế trên hệ thống SQL Server.'
                    ),
                    'parameters': {
                        'type': 'OBJECT',
                        'properties': {
                            'sql_query': {
                                'type': 'STRING',
                                'description': 'Câu lệnh SQL SELECT T-SQL an toàn (ví dụ: "SELECT TOP 20 * FROM dbo.FactSales WHERE Year = 2025").'
                            }
                        },
                        'required': ['sql_query']
                    }
                })

            if tools_list:
                payload['tools'] = [{'functionDeclarations': tools_list}]
                payload['toolConfig'] = {
                    'functionCallingConfig': {
                        'mode': 'AUTO'
                    }
                }

            reply_text = ""
            reply_segments = []
            api_call_count = 0
            continuation_count = 0
            max_continuations = 4
            try:
                while api_call_count < 3:
                    # ĐÃ SỬA: Tăng timeout từ 45 lên 90 giây để đủ thời gian generate response dài
                    response = requests.post(url, headers=headers, json=payload, timeout=90)
                    response.raise_for_status()
                    res_data = response.json()

                    # Check for functionCall parts (hỗ trợ cả camelCase và snake_case)
                    function_calls = []
                    model_response_parts = []
                    model_parts = []
                    if 'candidates' in res_data and len(res_data['candidates']) > 0:
                        candidate = res_data['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content']:
                            for part in candidate['content']['parts']:
                                f_call = part.get('functionCall') or part.get('function_call')
                                if f_call:
                                    function_calls.append(f_call)
                                    model_parts.append(part)

                    if function_calls:
                        tool_parts = []
                        for func_call in function_calls:
                            func_name = func_call.get('name')
                            func_args = func_call.get('args', {})

                            # Execute local function
                            if func_name == 'query_odoo_data':
                                result = self._execute_odoo_query(
                                    model=func_args.get('model'),
                                    domain=func_args.get('domain'),
                                    fields=func_args.get('fields')
                                )
                            elif func_name == 'query_sql_server_data':
                                result = self._execute_mssql_query(
                                    sql_query=func_args.get('sql_query'),
                                    topic=topic
                                )
                            else:
                                result = {'error': f"Unknown function '{func_name}'"}

                            function_response = {
                                'name': func_name,
                                'response': {'result': result}
                            }
                            if func_call.get('id'):
                                function_response['id'] = func_call.get('id')
                            tool_parts.append({'functionResponse': function_response})

                        # Append all functionCalls and functionResponses to contents history
                        contents.append({
                            'role': 'model',
                            'parts': model_parts
                        })
                        contents.append({
                            'role': 'user',
                            'parts': tool_parts
                        })

                        # Tắt function calling bằng cách xoá hẳn tools khỏi payload trong lần gọi tiếp theo
                        payload.pop('tools', None)
                        payload.pop('toolConfig', None)

                        payload['contents'] = contents
                        api_call_count += 1
                    else:
                        # ĐÃ SỬA: Cải tiến logic extract text để không bỏ sót part nào
                        current_reply_text = ""
                        if 'candidates' in res_data and len(res_data['candidates']) > 0:
                            candidate = res_data['candidates'][0]
                            if 'content' in candidate and 'parts' in candidate['content']:
                                all_parts_text = []
                                for part in candidate['content']['parts']:
                                    if 'text' in part:
                                        all_parts_text.append(part['text'])
                                    elif 'inlineData' in part:
                                        all_parts_text.append("[Hình ảnh]")

                                # Join với newline để giữ nguyên định dạng bảng Markdown
                                current_reply_text = "\n".join(all_parts_text)
                                if current_reply_text:
                                    reply_segments.append(current_reply_text)
                                    reply_text = "\n".join(reply_segments)

                        # ĐÃ SỬA: Kiểm tra finishReason để phát hiện nếu bị cắt cụt do MAX_TOKENS
                        if 'candidates' in res_data and len(res_data['candidates']) > 0:
                            candidate = res_data['candidates'][0]
                            finish_reason = candidate.get('finishReason', '')
                            if finish_reason == 'MAX_TOKENS':
                                _logger.warning("Gemini API response was truncated due to max tokens limit")
                                if current_reply_text and continuation_count < max_continuations:
                                    contents.append({
                                        'role': 'user',
                                        'parts': [{
                                            'text': (
                                                "Cau tra loi vua roi qua dai va bi cat do gioi han token. "
                                                "Hay viet lai mot cau tra loi hoan chinh, ngan gon hon, khong xin loi, "
                                                "khong nhac den viec bi cat, khong lap lai nhieu lan. "
                                                "Neu can bang Markdown, chi dung toi da 8 dong noi dung va moi o chi 1-2 cau ngan. "
                                                "Ket thuc bang phan ket luan ngan gon."
                                            )
                                        }]
                                    })
                                    payload['contents'] = contents
                                    reply_segments = []
                                    reply_text = ""
                                    continuation_count += 1
                                    continue
                                reply_text += "\n\n⚠️ *Lưu ý: Câu trả lời quá dài nên có thể bị cắt ngắn. Vui lòng hỏi cụ thể hơn (ví dụ: 'hãy nói chi tiết hơn về phần so sánh sức mạnh').*"

                        if not reply_text:
                            reply_text = "Không nhận được phản hồi hợp lệ từ Gemini API."
                        break

            except requests.exceptions.Timeout:
                # ĐÃ SỬA: Xử lý riêng lỗi timeout để thông báo rõ ràng cho người dùng
                _logger.error("Gemini API request timed out after 90 seconds")
                reply_text = "⏳ Câu hỏi của bạn cần thời gian xử lý lâu hơn dự kiến. Vui lòng thử lại với câu hỏi ngắn gọn hoặc cụ thể hơn."
            except requests.exceptions.HTTPError as e:
                response = getattr(e, 'response', None)
                error_details = self._extract_gemini_error(response, api_key) if response else {}
                _logger.error(
                    "Gemini API returned HTTP %s (%s): %s",
                    error_details.get('status_code'),
                    error_details.get('status'),
                    (error_details.get('message') or error_details.get('raw') or '')[:300],
                )
                reply_text = self._gemini_user_error_message(
                    status_code=error_details.get('status_code'),
                    error_status=error_details.get('status'),
                    error_message=error_details.get('message') or error_details.get('raw'),
                )
            except Exception as e:
                # VẤN ĐỀ 1: Không để traceback/exception gốc lộ ra reply_text (tránh lộ API key trong URL)
                err_msg = str(e)
                if api_key:
                    err_msg = err_msg.replace(api_key, "REDACTED")
                _logger.error("Error communicating with Gemini API: %s", err_msg)
                reply_text = "Đã xảy ra lỗi khi kết nối tới AI. Vui lòng thử lại sau."

            # Sanitize technical terms in the reply
            reply_text = self._sanitize_technical_terms(reply_text)

            # Safety net: Collapses excessive repeating characters (hyphens/spaces) generated by API repetition loops
            if reply_text:
                reply_text = re.sub(r'-{10,}', '----------', reply_text)
                reply_text = re.sub(r' {10,}', ' ', reply_text)

            # 9. Save bot's reply
            request.env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'model',
                'content': reply_text
            })
            bot_reply_saved = True

            # 10. Update Conversation Name if it's default
            if conversation.name in ('New Chat', 'Cuộc trò chuyện mới') and len(message) > 0:
                new_name = message[:40] + ('...' if len(message) > 40 else '')
                conversation.write({'name': new_name})

            return {
                'response': reply_text,
                'conversation_name': conversation.name
            }
        finally:
            if not bot_reply_saved:
                try:
                    orphan = request.env['topic_chatbot.message'].search([
                        ('conversation_id', '=', conversation.id),
                        ('role', '=', 'user'),
                    ], order='create_date desc, id desc', limit=1)
                    if orphan:
                        orphan.unlink()
                except Exception as e:
                    _logger.error("Failed to clean up orphan message: %s", str(e))
            conversation.sudo().write({'is_processing': False})

    @http.route('/topic_chatbot/ask_stream', type='http', auth='user', csrf=False, methods=['POST'])
    def ask_stream(self):
        """Send message to Gemini API with streaming SSE response."""
        import werkzeug

        data = json.loads(request.httprequest.data)
        conversation_id = data.get('conversation_id')
        message = data.get('message', '').strip()

        if not conversation_id or not message:
            return werkzeug.Response(
                json.dumps({'error': 'Missing conversation_id or message.'}),
                status=400,
                mimetype='application/json'
            )

        try:
            conversation_id_int = int(conversation_id)
        except (ValueError, TypeError):
            return werkzeug.Response(
                json.dumps({'error': 'Conversation not found or access denied.'}),
                status=404,
                mimetype='application/json'
            )

        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return werkzeug.Response(
                json.dumps({'error': 'Conversation not found or access denied.'}),
                status=404,
                mimetype='application/json'
            )

        # Rate limiting: Chặn spam gọi API
        if self._check_rate_limit(request.env, request.env.uid):
            return werkzeug.Response(
                json.dumps({'error': f'Bạn đã gửi quá {self.RATE_LIMIT_MAX_MESSAGES} câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại.'}),
                status=429,
                mimetype='application/json'
            )

        if conversation.is_processing:
            return werkzeug.Response(
                json.dumps({'error': 'Vui lòng chờ câu trả lời trước hoàn tất trước khi gửi câu hỏi mới.'}),
                status=409,
                mimetype='application/json'
            )

        conversation.sudo().write({'is_processing': True})

        topic = request.env['topic_chatbot.topic'].search([('id', '=', conversation.topic_id.id)])
        if not topic:
            conversation.sudo().write({'is_processing': False})
            return werkzeug.Response(
                json.dumps({'error': 'Truy cập vào chủ đề này bị từ chối hoặc không khả dụng.'}),
                status=403,
                mimetype='application/json'
            )

        request.env['topic_chatbot.message'].create({
            'conversation_id': conversation.id,
            'role': 'user',
            'content': message
        })

        chunks = self._retrieve_context(conversation.topic_id.id, message)
        context_str = "\n\n".join([
            (
                f"--- Nguồn: {chunk['document_name']}, đoạn {chunk['sequence']} ---\n"
                f"{chunk['content']}"
            )
            for chunk in chunks
        ])

        is_db_query = topic.is_db_query
        is_mssql_active = bool(
            topic.is_mssql_query or
            (topic.mssql_allowed_tables and topic.mssql_allowed_tables.strip()) or
            ('sql' in (topic.name or '').lower())
        )
        system_instruction = self._build_system_instruction(
            context_str,
            is_db_query=is_db_query,
            is_mssql_query=is_mssql_active,
            mssql_tables=topic.mssql_allowed_tables or ""
        )

        params = request.env['ir.config_parameter'].sudo()
        api_key = params.get_param('topic_chatbot.gemini_api_key')
        if not api_key:
            conversation.sudo().write({'is_processing': False})
            return werkzeug.Response(
                json.dumps({'error': 'Chưa cấu hình Gemini API Key. Vui lòng vào menu Cấu hình để nhập API Key.'}),
                status=400,
                mimetype='application/json'
            )
        model = params.get_param('topic_chatbot.gemini_model', default='gemini-3.6-flash')

        db_messages = request.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation.id)
        ], order='create_date desc')

        contents = []
        total_chars = 0
        MAX_CHARS = 30000
        
        for m in db_messages:
            cleaned_content = re.sub(r' {2,}', ' ', m.content or '').strip()
            if not cleaned_content:
                continue
            
            # Check character limit
            if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                break
                
            total_chars += len(cleaned_content)
            contents.insert(0, {
                'role': 'user' if m.role == 'user' else 'model',
                'parts': [{'text': cleaned_content}]
            })

        tools_list = []
        if is_db_query:
            tools_list.append({
                'name': 'query_odoo_data',
                'description': (
                    'Truy vấn đọc dữ liệu (Read-only) an toàn từ database Odoo '
                    'để tìm thông tin liên quan đến các dữ liệu nghiệp vụ: Nhân viên, '
                    'Phòng ban, Kết quả KPI tháng, Đánh giá KPI của lãnh đạo, KPI năm.\n'
                    'CHỈ sử dụng công cụ này khi người dùng hỏi các câu hỏi thực tế về dữ liệu '
                    'hệ thống Odoo (như KPI của một ai đó, xếp loại phòng ban, danh sách nhân viên, v.v.).'
                ),
                'parameters': {
                    'type': 'OBJECT',
                    'properties': {
                        'model': {
                            'type': 'STRING',
                            'description': (
                                'Tên model Odoo cần truy vấn. Chỉ chấp nhận các giá trị: '
                                '"hr.employee", "hr.department", "sonha.kpi.result.month", '
                                '"report.kpi.month", "sonha.kpi.year".'
                            )
                        },
                        'domain': {
                            'type': 'STRING',
                            'description': 'Mảng các điều kiện lọc dạng Odoo Domain (chuỗi JSON).'
                        },
                        'fields': {
                            'type': 'ARRAY',
                            'items': {'type': 'STRING'},
                            'description': 'Mảng chứa tên các trường thông tin cần lấy dữ liệu.'
                        }
                    },
                    'required': ['model', 'fields']
                }
            })

        if is_mssql_active:
            allowed_info = f" Danh sách bảng/view được phép: {topic.mssql_allowed_tables}." if topic.mssql_allowed_tables else ""
            tools_list.append({
                'name': 'query_sql_server_data',
                'description': (
                    'Truy vấn đọc dữ liệu (Read-only) an toàn từ CSDL Microsoft SQL Server bằng câu lệnh T-SQL SELECT.\n'
                    f'{allowed_info}\n'
                    'BẮT BUỘC sử dụng công cụ này khi người dùng hỏi về dữ liệu thực tế (sản phẩm, giá bán, tồn kho, danh mục, doanh số, v.v.).\n'
                    'LƯU Ý QUAN TRỌNG: Nếu bạn không chắc chắn về tên cột, HÃY luôn chạy lệnh "SELECT TOP 1 * FROM [TenBang]" '
                    'để lấy danh sách các cột trước, sau đó mới gọi lại công cụ này với điều kiện WHERE chính xác.'
                ),
                'parameters': {
                    'type': 'OBJECT',
                    'properties': {
                        'sql_query': {
                            'type': 'STRING',
                            'description': 'Câu lệnh SQL SELECT T-SQL an toàn (ví dụ: "SELECT TOP 20 * FROM dbo.SanPham").'
                        }
                    },
                    'required': ['sql_query']
                }
            })

        tools = [{'functionDeclarations': tools_list}] if tools_list else None

        registry = request.env.registry
        user_id = request.env.uid
        conversation_id = conversation.id
        topic_id = topic.id

        def generate():
            import time
            final_reply = ""
            continuation_count = 0
            max_continuations = 4
            clean_model = (model or 'gemini-3.6-flash').replace('models/', '').strip()
            deprecated_model_map = {
                'gemini-1.5-flash': 'gemini-3.5-flash-lite',
                'gemini-1.5-pro': 'gemini-3.1-pro-preview',
                'gemini-2.0-flash': 'gemini-3.6-flash',
                'gemini-2.0-flash-001': 'gemini-3.6-flash',
                'gemini-2.0-flash-lite': 'gemini-3.5-flash-lite',
                'gemini-2.0-flash-lite-001': 'gemini-3.5-flash-lite',
            }
            clean_model = deprecated_model_map.get(clean_model, clean_model) or 'gemini-3.6-flash'

            models_to_try = [clean_model]
            if clean_model != 'gemini-3.5-flash-lite':
                models_to_try.append('gemini-3.5-flash-lite')

            req_headers = {'Content-Type': 'application/json'}
            local_contents = list(contents)

            try:
                while continuation_count <= max_continuations:
                    payload = {
                        'contents': local_contents,
                        'systemInstruction': {'parts': [{'text': system_instruction}]},
                        'generationConfig': {
                            'maxOutputTokens': 8192
                        }
                    }
                    if tools and continuation_count == 0:
                        # Lần đầu: cho phép Gemini gọi tool. Không truyền tool trong các lần sau để ép ngừng.
                        payload['tools'] = tools
                        payload['toolConfig'] = {
                            'functionCallingConfig': {
                                'mode': 'AUTO'
                            }
                        }

                    function_calls = []
                    model_response_parts = []
                    segment_text = ""
                    stream_success = False
                    last_error_message = self._gemini_user_error_message()
                    fatal_api_error = False

                    for target_model in models_to_try:
                        stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:streamGenerateContent?key={api_key}&alt=sse"
                        for attempt in range(3):
                            try:
                                resp = requests.post(stream_url, headers=req_headers, json=payload, stream=True, timeout=90)
                                _logger.info("ask_stream: Gemini API response status=%d (model=%s, attempt=%d, continuation=%d)", 
                                             resp.status_code, target_model, attempt + 1, continuation_count)
                                if resp.status_code == 200:
                                    stream_success = True
                                    resp.encoding = 'utf-8'
                                    for raw_line in resp.iter_lines(decode_unicode=True):
                                        if not raw_line:
                                            continue
                                        if raw_line.startswith('data: '):
                                            event_data = raw_line[6:]
                                            if event_data == '[DONE]':
                                                break
                                            try:
                                                chunk = json.loads(event_data)
                                                candidate = chunk.get('candidates', [{}])[0]
                                                content_parts = candidate.get('content', {}).get('parts', [])
                                                for part in content_parts:
                                                    model_response_parts.append(part)
                                                    if 'text' in part:
                                                        token = part['text']
                                                        segment_text += token
                                                        final_reply += token
                                                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                                                    f_call = part.get('functionCall') or part.get('function_call')
                                                    if f_call:
                                                        function_calls.append(f_call)
                                            except json.JSONDecodeError:
                                                continue
                                    resp.close()
                                    break
                                elif resp.status_code == 429:
                                    error_details = self._extract_gemini_error(resp, api_key)
                                    last_error_message = self._gemini_user_error_message(
                                        status_code=error_details.get('status_code'),
                                        error_status=error_details.get('status'),
                                        error_message=error_details.get('message') or error_details.get('raw'),
                                    )
                                    retry_after = resp.headers.get('Retry-After')
                                    resp.close()
                                    _logger.warning("Gemini Stream API 429 Rate Limit (%s, attempt %s/3). Retrying in 2s...", target_model, attempt + 1)
                                    try:
                                        sleep_seconds = min(max(int(retry_after or 0), 2), 15)
                                    except (TypeError, ValueError):
                                        sleep_seconds = min(2 ** (attempt + 1), 8)
                                    time.sleep(sleep_seconds)
                                    continue
                                else:
                                    error_details = self._extract_gemini_error(resp, api_key)
                                    last_error_message = self._gemini_user_error_message(
                                        status_code=error_details.get('status_code'),
                                        error_status=error_details.get('status'),
                                        error_message=error_details.get('message') or error_details.get('raw'),
                                    )
                                    is_config_error = resp.status_code in (400, 401, 403, 404)
                                    err_body = error_details.get('message') or error_details.get('raw')
                                    status_text = error_details.get('status')
                                    status_code = resp.status_code
                                    resp.close()
                                    _logger.error(
                                        "Gemini Stream API returned HTTP %d %s (%s): %s",
                                        status_code,
                                        status_text,
                                        target_model,
                                        (err_body or '')[:300],
                                    )
                                    if is_config_error:
                                        fatal_api_error = True
                                    break
                            except requests.exceptions.Timeout:
                                _logger.warning("Gemini Stream API request timed out (%s, attempt %s/3)", target_model, attempt + 1)
                                last_error_message = "Gemini API phản hồi quá lâu. Vui lòng thử lại với câu hỏi ngắn hơn hoặc thử lại sau."
                                break
                            except Exception as req_err:
                                err_msg = str(req_err)
                                if api_key:
                                    err_msg = err_msg.replace(api_key, "REDACTED")
                                _logger.warning("Gemini Stream API connection error (%s): %s", target_model, err_msg)
                                last_error_message = self._gemini_user_error_message()
                                break

                        if stream_success or fatal_api_error:
                            break

                    if not stream_success:
                        yield f"data: {json.dumps({'type': 'error', 'content': last_error_message}, ensure_ascii=False)}\n\n"
                        return

                    if function_calls:
                        _logger.info("ask_stream: Processing %d function_calls", len(function_calls))
                        yield f"data: {json.dumps({'type': 'status', 'content': 'Đang tra cứu dữ liệu...'}, ensure_ascii=False)}\n\n"

                        import odoo
                        tool_parts = []
                        with registry.cursor() as cr:
                            gen_env = odoo.api.Environment(cr, user_id, {})
                            gen_topic = gen_env['topic_chatbot.topic'].browse(topic_id)
                            for fc in function_calls:
                                func_name = fc.get('name')
                                func_args = fc.get('args', {})
                                if func_name == 'query_odoo_data':
                                    result = self._execute_odoo_query(
                                        model=func_args.get('model'),
                                        domain=func_args.get('domain'),
                                        fields=func_args.get('fields'),
                                        env=gen_env
                                    )
                                elif func_name == 'query_sql_server_data':
                                    sql_query = func_args.get('sql_query', '')
                                    safe_query = sql_query.encode('ascii', 'backslashreplace').decode('ascii') if sql_query else ''
                                    _logger.info("ask_stream: Gemini called query_sql_server_data with query: %s", safe_query)
                                    result = self._execute_mssql_query(
                                        sql_query=sql_query,
                                        topic=gen_topic,
                                        env=gen_env
                                    )
                                    res_preview = str(result)[:200]
                                    safe_preview = res_preview.encode('ascii', 'backslashreplace').decode('ascii')
                                    _logger.info("ask_stream: SQL Server result preview: %s", safe_preview)
                                else:
                                    result = {'error': f"Unknown function '{func_name}'"}
                                function_response = {
                                    'name': func_name,
                                    'response': {'result': result}
                                }
                                if fc.get('id'):
                                    function_response['id'] = fc.get('id')
                                tool_parts.append({'functionResponse': function_response})

                        _logger.info("ask_stream: tool_parts count=%d, model_response_parts count=%d", len(tool_parts), len(model_response_parts))
                        local_contents.append({'role': 'model', 'parts': model_response_parts})
                        local_contents.append({'role': 'user', 'parts': tool_parts})
                        continuation_count += 1
                        _logger.info("ask_stream: continuation #%d, sending tool results back to Gemini", continuation_count)
                    else:
                        _logger.info("ask_stream: no function_calls, final_reply length=%d", len(final_reply))
                        break

                if not final_reply:
                    _logger.warning("ask_stream: final_reply is EMPTY after %d continuations", continuation_count)
                    final_reply = "Đã tra cứu thành công dữ liệu từ SQL Server nhưng không nhận được phản hồi tổng hợp từ AI. Vui lòng thử lại."
                    yield f"data: {json.dumps({'type': 'token', 'content': final_reply}, ensure_ascii=False)}\n\n"

                final_reply = self._sanitize_technical_terms(final_reply)
                if final_reply:
                    final_reply = re.sub(r'-{10,}', '----------', final_reply)
                    final_reply = re.sub(r' {10,}', ' ', final_reply)

                # Mở cursor và env mới để ghi DB tránh lỗi unbound request object
                import odoo
                with registry.cursor() as cr:
                    env = odoo.api.Environment(cr, user_id, {})
                    env['topic_chatbot.message'].create({
                        'conversation_id': conversation_id,
                        'role': 'model',
                        'content': final_reply
                    })

                    conv = env['topic_chatbot.conversation'].browse(conversation_id)
                    if conv.name in ('New Chat', 'Cuộc trò chuyện mới') and len(message) > 0:
                        new_name = message[:40] + ('...' if len(message) > 40 else '')
                        conv.write({'name': new_name})
                    conv_name = conv.name

                yield f"data: {json.dumps({'type': 'done', 'conversation_name': conv_name}, ensure_ascii=False)}\n\n"

            finally:
                # Giải phóng trạng thái is_processing bằng cursor mới
                import odoo
                try:
                    with registry.cursor() as cr:
                        env = odoo.api.Environment(cr, user_id, {})
                        conv = env['topic_chatbot.conversation'].browse(conversation_id)
                        conv.sudo().write({'is_processing': False})
                except Exception as ex:
                    _logger.error("Failed to reset is_processing status: %s", str(ex))

        headers = {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
        return werkzeug.Response(generate(), headers=headers, mimetype='text/event-stream')

    def _retrieve_context(self, topic_id, message, limit=5):
        """Retrieve relevant chunks using Vector Embedding Semantic Search with FTS fallback."""
        import json
        import math

        try:
            topic_id_int = int(topic_id)
        except (ValueError, TypeError):
            return []

        # Verify topic access first using ORM search (applying record rules automatically)
        topic = request.env['topic_chatbot.topic'].search([('id', '=', topic_id_int)])
        if not topic:
            return []

        # Clean message check
        cleaned_msg = message.strip()
        if not cleaned_msg:
            return []

        params = request.env['ir.config_parameter'].sudo()
        api_key = params.get_param('topic_chatbot.gemini_api_key')
        embedding_model = params.get_param('topic_chatbot.embedding_model', default='gemini-embedding-2')
        if embedding_model in ('text-embedding-004', 'embedding-001') or not embedding_model:
            embedding_model = 'gemini-embedding-2'

        # 1. Attempt Vector Semantic Search using Gemini Embedding API & Cosine Similarity
        if api_key:
            try:
                query_emb_json = request.env['topic_chatbot.chunk']._generate_embedding(
                    cleaned_msg, api_key, embedding_model
                )
                if query_emb_json:
                    query_v = json.loads(query_emb_json)

                    sql_query = """
                        SELECT c.id, c.content, c.sequence, d.name, c.embedding_vector <=> %s AS distance
                          FROM topic_chatbot_chunk c
                          JOIN topic_chatbot_document d ON d.id = c.document_id
                         WHERE c.topic_id = %s AND c.embedding_vector IS NOT NULL
                      ORDER BY c.embedding_vector <=> %s
                         LIMIT %s
                    """
                    request.env.cr.execute(sql_query, (query_emb_json, topic.id, query_emb_json, limit))
                    rows = request.env.cr.fetchall()

                    vector_results = []
                    for row in rows:
                        chunk_id, content, sequence, doc_name, distance = row
                        sim = 1.0 - float(distance)
                        if sim > 0.20:  # Minimum similarity threshold
                            vector_results.append((sim, {
                                'id': chunk_id,
                                'content': content,
                                'sequence': sequence or 1,
                                'document_name': doc_name or 'Unknown Document',
                            }))

                    if vector_results:
                        _logger.info("PgVector Semantic Search found %d relevant chunks for topic %s", len(vector_results), topic.id)
                        return [item[1] for item in vector_results]
            except Exception as e:
                _logger.warning("PgVector Semantic Search error, falling back to FTS: %s", str(e))

        # 2. Fallback to Full-Text Search (FTS) & Token score matching
        words = [w for w in re.sub(r'[^\w\s]', '', cleaned_msg.lower()).split() if len(w) > 1]
        STOP_WORDS = {
            'xin', 'chào', 'hello', 'hi', 'hey', 'tôi', 'bạn', 'này', 'cái', 'cho',
            'hỏi', 'là', 'và', 'có', 'không', 'ở', 'trong', 'được', 'người', 'những',
            'các', 'như', 'bot', 'ad', 'admin', 'ai', 'chỉ', 'giúp', 'với', 'ạ',
            'gì', 'nào', 'đâu', 'sao', 'thế', 'nếu', 'thì', 'mà', 'của', 'để', 'từ'
        }
        custom_stop_words = params.get_param('topic_chatbot.stop_words', '')
        if custom_stop_words:
            for w in custom_stop_words.split(','):
                w_clean = w.strip().lower()
                if w_clean:
                    STOP_WORDS.add(w_clean)
        meaningful_words = [w for w in words if w not in STOP_WORDS]

        if not meaningful_words:
            return []

        # Attempt PostgreSQL tsvector text search
        try:
            sql_query = """
                SELECT c.id, c.content, c.sequence, d.name
                  FROM topic_chatbot_chunk c
                  JOIN topic_chatbot_document d ON d.id = c.document_id
                 WHERE c.topic_id = %s
                   AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', %s)
              ORDER BY c.document_id, c.sequence, c.id
                 LIMIT %s
            """
            request.env.cr.execute(sql_query, (topic.id, " ".join(meaningful_words), limit))
            results = request.env.cr.fetchall()
            if results:
                return [
                    {
                        'id': row[0],
                        'content': row[1],
                        'sequence': row[2] or 1,
                        'document_name': row[3] or 'Unknown Document',
                    }
                    for row in results
                ]
        except Exception as e:
            _logger.warning("Postgres tsvector search failed, falling back to python match: %s", str(e))

        # Python-based token score matching (Fallback 2)
        def escape_like(word):
            return word.replace('=', '==').replace('%', '=%').replace('_', '=_')

        escaped_words = [escape_like(w) for w in meaningful_words]
        like_clauses = " OR ".join(["c.content ILIKE %s ESCAPE '='"] * len(escaped_words))
        sql_query = f"""
            SELECT c.id, c.content, c.sequence, d.name
              FROM topic_chatbot_chunk c
              JOIN topic_chatbot_document d ON d.id = c.document_id
             WHERE c.topic_id = %s AND ({like_clauses})
             LIMIT 100
        """
        params_sql = [topic.id] + [f"%{word}%" for word in escaped_words]
        try:
            request.env.cr.execute(sql_query, params_sql)
            results = request.env.cr.fetchall()
        except Exception as e:
            _logger.error("Fallback SQL search failed: %s", str(e))
            results = []

        scored_chunks = []
        for row in results:
            chunk_id, content, sequence, doc_name = row
            content_lower = content.lower()
            score = sum(content_lower.count(word) for word in meaningful_words)
            if score > 0:
                scored_chunks.append((score, {
                    'id': chunk_id,
                    'content': content,
                    'sequence': sequence or 1,
                    'document_name': doc_name or 'Unknown Document',
                }))

        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_chunks[:limit]]
