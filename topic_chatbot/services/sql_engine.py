# -*- coding: utf-8 -*-
import json
import logging
import re
import time
from datetime import datetime as dt, date as dt_date
import decimal
try:
    from odoo.http import request
except ImportError:
    request = None

_logger = logging.getLogger(__name__)


def execute_odoo_query(model, domain=None, fields=None, env=None):
    """Execute a safe, read-only Odoo search_read query using the given or current user's environment."""
    if env is None:
        try:
            env = request.env
        except Exception:
            return {'error': 'Không thể khởi tạo môi trường truy vấn Odoo.'}

    model_alias_map = {
        'employees': 'hr.employee',
        'departments': 'hr.department',
        'kpi_month_results': 'sonha.kpi.result.month',
        'kpi_month_report': 'report.kpi.month',
        'kpi_year_results': 'sonha.kpi.year',
    }
    actual_model = model_alias_map.get(str(model).strip().lower(), model)

    safe_models = [
        'hr.employee',
        'hr.department',
        'sonha.kpi.result.month',
        'report.kpi.month',
        'sonha.kpi.year'
    ]

    if actual_model not in safe_models:
        return {'error': 'Loại dữ liệu này không thuộc phạm vi truy vấn được phép hoặc bị hạn chế vì lý do bảo mật.'}

    model = actual_model

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
        _logger.info(
            "[DB_QUERY_AUDIT] execute_odoo_query: model='%s', domain=%s, fields=%s",
            model, clean_domain, clean_fields
        )
        records = model_obj.search_read(clean_domain, clean_fields, limit=80)
        _logger.info("[DB_QUERY_AUDIT] execute_odoo_query: returned %d record(s)", len(records))
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


def execute_mssql_query(sql_query, topic=None, env=None):
    """Execute a safe, read-only T-SQL SELECT query on Microsoft SQL Server."""
    if env is None:
        try:
            env = request.env
        except Exception:
            return {'error': 'Không thể khởi tạo môi trường truy vấn Odoo.'}

    from odoo.addons.topic_chatbot.models import crypto_utils as _crypto
    
    # Determine connection
    if topic and topic.mssql_connection_id:
        conn_record = topic.mssql_connection_id
        if not conn_record.active:
            return {'error': f'Kết nối SQL Server "{conn_record.name}" đang bị vô hiệu hóa.'}
        host = conn_record.host or 'localhost'
        port = conn_record.port or '1433'
        db = conn_record.database or ''
        user = conn_record.user or ''
        raw_password = conn_record.password or ''
        password = _crypto.decrypt_value(env, raw_password) if _crypto.is_encrypted(raw_password) else raw_password
        driver = conn_record.driver or 'ODBC Driver 17 for SQL Server'
    else:
        params = env['ir.config_parameter'].sudo()
        mssql_enabled = params.get_param('topic_chatbot.mssql_enabled', 'False').lower() in ('true', '1')
        if not mssql_enabled:
            return {'error': 'Tính năng kết nối SQL Server chung đã bị tắt.'}
        host = params.get_param('topic_chatbot.mssql_host') or 'localhost'
        port = params.get_param('topic_chatbot.mssql_port') or '1433'
        db = params.get_param('topic_chatbot.mssql_db') or ''
        user = params.get_param('topic_chatbot.mssql_user') or ''
        raw_password = params.get_param('topic_chatbot.mssql_password') or ''
        password = _crypto.decrypt_value(env, raw_password)
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
        r'\bREVOKE\b', r'\bMERGE\b', r'\bSELECT\s+INTO\b', r'\bSP_\b', r'\bXP_\b'
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

        cte_names = set(
            name.strip().lower()
            for name in re.findall(r'\bWITH\s+(\w+)\s+AS\s*\(', clean_query_no_comments, flags=re.IGNORECASE)
        )
        cte_names.update(
            name.strip().lower()
            for name in re.findall(r',\s*(\w+)\s+AS\s*\(', clean_query_no_comments, flags=re.IGNORECASE)
        )
        allowed_tables.update(cte_names)

        table_refs = re.findall(
            r'\b(?:FROM|JOIN)\s+((?:\[[^\]]+\]|\w+)(?:\s*\.\s*(?:\[[^\]]+\]|\w+)){0,2})',
            clean_query_no_comments,
            flags=re.IGNORECASE
        )
        for table_ref in table_refs:
            raw_ref = table_ref.strip().split()[0]
            normalized_ref = raw_ref.replace('[', '').replace(']', '').replace(' ', '').lower()
            if normalized_ref in ('select', 'with', ''):
                continue
            if normalized_ref not in allowed_tables and normalized_ref.split('.')[-1] not in allowed_tables:
                return {
                    'error': (
                        f'Bảng/view "{table_ref}" trong câu lệnh SQL không nằm trong danh sách '
                        f'được phép của chủ đề này. Vui lòng liên hệ Admin để cập nhật danh sách bảng cho phép.'
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
                priority = []
                others = []
                for d in installed:
                    dl = d.lower()
                    if 'sql server' not in dl:
                        continue
                    if 'native client' in dl:
                        continue
                    if 'odbc driver' in dl:
                        priority.append(d)
                    else:
                        others.append(d)
                drivers_to_try = sorted(priority, reverse=True) + others
            except Exception:
                pass

            if driver and driver not in drivers_to_try:
                drivers_to_try.append(driver)
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

        start_time = time.time()
        cursor = conn.cursor()
        _logger.info("[DB_QUERY_AUDIT] execute_mssql_query: executing SQL: %s", clean_query_no_comments)
        cursor.execute(clean_query_no_comments)

        if not cursor.description:
            exec_time = int((time.time() - start_time) * 1000)
            if topic:
                env['topic_chatbot.mssql_log'].sudo().create({
                    'topic_id': topic.id,
                    'query_text': clean_query_no_comments,
                    'is_success': False,
                    'error_msg': 'Câu lệnh không trả về dữ liệu.',
                    'execution_time_ms': exec_time,
                })
            return {'error': 'Câu lệnh không trả về dữ liệu.'}

        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchmany(100)

        results = []
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

        exec_time = int((time.time() - start_time) * 1000)
        _logger.info(
            "[DB_QUERY_AUDIT] execute_mssql_query: returned %d row(s) in %dms",
            len(results), exec_time
        )
        if topic:
            env['topic_chatbot.mssql_log'].sudo().create({
                'topic_id': topic.id,
                'query_text': clean_query_no_comments,
                'is_success': True,
                'error_msg': '',
                'execution_time_ms': exec_time,
            })

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
        if 'start_time' in locals():
            exec_time = int((time.time() - start_time) * 1000)
        else:
            exec_time = 0
        if topic:
            env['topic_chatbot.mssql_log'].sudo().create({
                'topic_id': topic.id,
                'query_text': clean_query_no_comments,
                'is_success': False,
                'error_msg': str(e),
                'execution_time_ms': exec_time,
            })
        return {'error': f'Lỗi thực thi truy vấn SQL Server: {str(e)}'}
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def execute_safe_table_query(query_str, env=None, max_limit=100):
    """Execute a safe, read-only SQL query on PostgreSQL for tabular data.
    
    Security & Validation Guarantees:
    1. Read-Only Guard: Strictly rejects write/DDL keywords (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.).
    2. Enforces statement_timeout = 5000 (5 seconds) to prevent long-running queries from blocking PostgreSQL.
    3. Enforces hard LIMIT <= max_limit (default 100 rows).
    """
    if env is None:
        try:
            env = request.env
        except Exception:
            return {'error': 'Không thể khởi tạo môi trường truy vấn Odoo.'}

    if not query_str or not isinstance(query_str, str):
        return {'error': 'Câu truy vấn không hợp lệ.'}

    clean_query = query_str.strip()
    # Strip comments
    clean_query = re.sub(r'--.*$', '', clean_query, flags=re.MULTILINE)
    clean_query = re.sub(r'/\*.*?\*/', '', clean_query, flags=re.DOTALL).strip()

    # Reject non-SELECT queries
    if not re.match(r'^\s*SELECT\b', clean_query, re.IGNORECASE):
        return {'error': 'Chỉ cho phép thực thi câu lệnh truy vấn đọc dữ liệu (SELECT).'}

    # Forbidden mutation / DDL keywords
    forbidden_pattern = r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|EXEC|EXECUTE|CREATE|GRANT|REVOKE|INTO|SET|BEGIN|COMMIT|ROLLBACK)\b'
    if re.search(forbidden_pattern, clean_query, re.IGNORECASE):
        return {'error': 'Phát hiện từ khóa không an toàn hoặc cố gắng thay đổi dữ liệu.'}

    # Enforce LIMIT
    if not re.search(r'\bLIMIT\s+\d+\b', clean_query, re.IGNORECASE):
        clean_query = f"{clean_query.rstrip(';')} LIMIT {max_limit}"
    else:
        limit_match = re.search(r'\bLIMIT\s+(\d+)\b', clean_query, re.IGNORECASE)
        if limit_match and int(limit_match.group(1)) > max_limit:
            clean_query = re.sub(r'\bLIMIT\s+\d+\b', f'LIMIT {max_limit}', clean_query, flags=re.IGNORECASE)

    try:
        start_time = time.time()
        env.cr.execute("SET LOCAL statement_timeout = 5000;")
        env.cr.execute(clean_query)
        columns = [desc[0] for desc in env.cr.description] if env.cr.description else []
        rows = env.cr.fetchall()
        exec_time = int((time.time() - start_time) * 1000)

        results = []
        for row in rows:
            record_dict = {}
            for col_idx, col_name in enumerate(columns):
                val = row[col_idx]
                if isinstance(val, (dt, dt_date)):
                    val = val.isoformat()
                elif isinstance(val, decimal.Decimal):
                    val = float(val)
                record_dict[col_name] = val
            results.append(record_dict)

        return {
            'data': results,
            'count': len(results),
            'columns': columns,
            'execution_time_ms': exec_time,
            'notice': f'Dữ liệu được truy vấn an toàn (tối đa {max_limit} dòng).'
        }
    except Exception as e:
        _logger.warning("Safe Table Query error: %s (Query: %s)", str(e), clean_query[:150])
        return {'error': f'Lỗi thực thi truy vấn bảng dữ liệu: {str(e)}'}


def _normalize_col_name(name):
    """Normalize column name for fuzzy/case-insensitive/diacritics-insensitive matching."""
    if not name:
        return ""
    s = str(name).strip().lower()
    # Simple Vietnamese diacritics stripping for robust matching
    trans = str.maketrans(
        "àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ",
        "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    )
    return s.translate(trans)


def _parse_markdown_sheets(text):
    """Parse Markdown tables grouped by sheet headers from document text_content.
    Returns: list of dicts: [{'sheet_name': str, 'columns': [str], 'rows': [{col: val}]}]
    """
    if not text:
        return []

    sheets = []
    # Split by sheet header pattern: --- Sheet: SheetName --- (allowing hyphens and accents)
    sheet_blocks = re.split(r'---\s*Sheet:\s*(.+?)\s*---\s*(?:\n|$)', text)
    if len(sheet_blocks) > 1:
        for i in range(1, len(sheet_blocks), 2):
            s_name = sheet_blocks[i].strip()
            s_body = sheet_blocks[i + 1]
            parsed = _parse_single_markdown_table(s_body)
            if parsed:
                parsed['sheet_name'] = s_name
                sheets.append(parsed)
    else:
        parsed = _parse_single_markdown_table(text)
        if parsed:
            parsed['sheet_name'] = 'Sheet1'
            sheets.append(parsed)

    return sheets


def _clean_header_name(col):
    """Extract primary column name from multi-line/merged header strings."""
    if not col:
        return ""
    c = str(col).strip()
    if ' / ' in c:
        parts = [p.strip() for p in c.split(' / ') if p.strip()]
        if len(parts) > 1:
            last = parts[-1]
            if len(last) <= 30 and not any(k in last.lower() for k in ('bảng phân', 'quy định', 'phụ lục', 'dự thảo', 'hướng dẫn')):
                return last
            return parts[0]
    return c


def _find_best_header_row(table_lines):
    """Detect true header row index from the top lines of a Markdown table."""
    best_idx = 0
    best_score = -1
    for i in range(min(len(table_lines), 20)):
        cells = [c.strip() for c in table_lines[i].strip('|').split('|')]
        non_empty = [c for c in cells if c and not re.match(r'^-+$', c)]
        if len(non_empty) < 2:
            continue
        distinct = set(non_empty)
        distinct_ratio = len(distinct) / len(non_empty)
        has_kw = any(any(k in c.lower() for k in ('tt', 'stt', 'nội dung', 'các vấn đề', 'phạm vi', 'ct', 'pct', 'tgđ', 'chủ tịch', 'mã', 'tên', 'lĩnh vực')) for c in non_empty)
        score = distinct_ratio * (2.0 if has_kw else 1.0)
        if score > best_score and distinct_ratio >= 0.5:
            best_score = score
            best_idx = i
    return best_idx


def _parse_single_markdown_table(body):
    """Parse a single Markdown table block into columns and rows."""
    raw_lines = [ln.strip() for ln in body.split('\n') if ln.strip()]
    if not raw_lines:
        return None

    # Merge lines broken by embedded newlines inside cells
    merged_lines = []
    for ln in raw_lines:
        if ln.startswith('|') and ln.endswith('|'):
            merged_lines.append(ln)
        elif merged_lines:
            merged_lines[-1] = merged_lines[-1][:-1] + ' ' + ln.strip().strip('|') + '|'
        elif ln.startswith('|'):
            merged_lines.append(ln + '|')

    table_lines = [ln for ln in merged_lines if ln.startswith('|') and ln.endswith('|')]
    if len(table_lines) < 2:
        return None

    h_idx = _find_best_header_row(table_lines)
    raw_header = [c.strip() for c in table_lines[h_idx].strip('|').split('|')]

    seen = {}
    header = []
    for idx, col in enumerate(raw_header):
        cleaned = _clean_header_name(col)
        c = cleaned or f"Cột_{idx+1}"
        if c in seen:
            seen[c] += 1
            header.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 1
            header.append(c)

    if not header:
        return None

    data_lines = table_lines[h_idx + 1:]
    rows = []
    for line in data_lines:
        if re.match(r'^\|(?:\s*:?-+:?\s*\|)+$', line):
            continue
        vals = [c.strip() for c in line.strip('|').split('|')]
        row_dict = {}
        for idx, col in enumerate(header):
            row_dict[col] = vals[idx] if idx < len(vals) else ""
        rows.append(row_dict)

    return {'columns': header, 'rows': rows}


def execute_structured_query_object(env, topic, structured_query_obj, max_limit=100):
    """Safely execute a Structured Query Object against the tabular documents of a topic.
    
    Guarantees (Sections 19, 20, 21):
    - Schema Validation: Whitelist sheet and column names.
    - Operator Whitelist: ('=', '!=', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'IN', 'CONTAINS').
    - Parameterized & Safe Evaluation: No raw SQL injection possible.
    - Result Semantics: Returns all matching rows, count computed before safety limit.
    - Full Observability: Logs all 8 [STRUCTURED_QUERY] lines and 6 [SQ_DEBUG] steps.
    - Error safety: Returns error dict, never raises uncaught exceptions (no silent fallback).
    """
    start_time = time.time()
    _logger.info("[STRUCTURED_QUERY] start")

    try:
        if not structured_query_obj or not isinstance(structured_query_obj, dict):
            raise ValueError("Structured Query Object không hợp lệ.")

        # 1. Resolve topic record
        if isinstance(topic, (int, str)):
            topic_rec = env['topic_chatbot.topic'].browse(int(topic))
        else:
            topic_rec = topic

        if not topic_rec or not topic_rec.exists():
            raise ValueError(f"Topic {topic} không tồn tại hoặc không có quyền truy cập.")

        query_type = str(structured_query_obj.get('query_type') or 'LIST').upper()
        req_sheet = structured_query_obj.get('sheet')
        filters = structured_query_obj.get('filters') or []
        req_select = structured_query_obj.get('select') or []
        aggregate = structured_query_obj.get('aggregate')
        lookup_item = structured_query_obj.get('lookup_item')
        target_action = str(structured_query_obj.get('target_action') or 'A').upper()

        ALLOWED_OPERATORS = ('=', '!=', '>', '<', '>=', '<=', 'LIKE', 'ILIKE', 'IN', 'CONTAINS')
        for flt in filters:
            op = str(flt.get('operator') or '=').upper()
            if op not in ALLOWED_OPERATORS:
                raise ValueError(f"Toán tử '{op}' không nằm trong whitelist cho phép.")

        # 2. Extract sheets from topic documents
        docs = topic_rec.document_ids.filtered(lambda d: d.state in ('done', 'partial'))
        all_sheets = []
        for d in docs:
            sheets = _parse_markdown_sheets(d.text_content)
            for s in sheets:
                s['document_name'] = d.name
                all_sheets.append(s)

        if not all_sheets:
            # Check if there are schema summary chunks in chunk table
            env.cr.execute("""
                SELECT c.content, d.name
                  FROM topic_chatbot_chunk c
                  JOIN topic_chatbot_document d ON d.id = c.document_id
                 WHERE c.topic_id = %s
                   AND c.content LIKE '%%[SHEET_SUMMARY_SCHEMA]%%'
                 LIMIT 5
            """, (topic_rec.id,))
            schema_rows = env.cr.fetchall()
            if not schema_rows:
                raise ValueError("Chủ đề hiện chưa có tài liệu bảng tính (Excel/CSV) đã xử lý xong.")

        # 3. Filter sheets if specific sheet requested
        target_sheets = all_sheets
        if req_sheet:
            norm_req_sheet = _normalize_col_name(req_sheet)
            target_sheets = [s for s in all_sheets if norm_req_sheet in _normalize_col_name(s['sheet_name'])]
            if not target_sheets:
                # Fallback to all sheets if sheet name wasn't exact
                target_sheets = all_sheets

        sheet_name_str = target_sheets[0]['sheet_name'] if len(target_sheets) == 1 else (req_sheet or "Tất cả")
        _logger.info("[STRUCTURED_QUERY] sheet=%s", sheet_name_str)
        _logger.info("[STRUCTURED_QUERY] filters=%s", json.dumps(filters, ensure_ascii=False))

        # 4. Filter rows per sheet (guaranteeing column isolation across sheets)
        matched_by_sheet = {}
        for s in target_sheets:
            s_name = s.get('sheet_name', 'Sheet1')
            s_cols = s.get('columns', [])
            s_rows = s.get('rows', [])

            _logger.info(
                "[SQ_DEBUG][SHEET]\nsheet_name = %s\ntotal_rows = %d\ncolumns = %s",
                s_name, len(s_rows), json.dumps(s_cols, ensure_ascii=False)
            )

            norm_cols_map = {_normalize_col_name(c): c for c in s_cols}

            if query_type == 'LOOKUP':
                norm_lookup = _normalize_col_name(lookup_item or "")
                raw_tokens = re.findall(r'\w+', norm_lookup)
                STOP_WORDS = {'cac', 'cua', 'hoac', 'va', 'cho', 'doi', 'voi', 'nhung', 'nao', 'o', 'tai', 'theo'}
                tokens = [t for t in raw_tokens if len(t) >= 2 and t not in STOP_WORDS]
                clean_lookup = " ".join(tokens)

                scored_matches = []
                for r_idx, row in enumerate(s_rows):
                    row_vals_str = " ".join(str(v) for v in row.values() if v)
                    norm_row_str = _normalize_col_name(row_vals_str)
                    clean_row = " ".join(re.findall(r'\w+', norm_row_str))

                    score = 0.0
                    if norm_lookup and norm_lookup in norm_row_str:
                        score = 1.0
                    elif clean_lookup and clean_lookup in clean_row:
                        score = 1.0
                    elif tokens:
                        matched_t = sum(1 for t in tokens if t in norm_row_str)
                        token_ratio = matched_t / len(tokens)
                        if token_ratio >= 0.7:
                            score = token_ratio

                    if score >= 0.7:
                        # Compound RACI-aware extraction:
                        # Cells may contain compound values like "P/R", "A/R", "P/E".
                        # Decompose by splitting on '/' and matching each component.
                        # 'E' is treated as alias for 'R' (Execute ≈ Responsible).
                        approvers = []
                        responsible = []
                        proposers = []
                        informed = []
                        for col, val in row.items():
                            raw_val = str(val).strip().upper()
                            if not raw_val:
                                continue
                            # Split compound values: "P/R" → ["P", "R"], "A" → ["A"], "I+" → ["I+"]
                            parts = [p.strip() for p in raw_val.replace('+', '+§').split('/')]
                            parts = [p.replace('+§', '+') for p in parts if p.replace('+§', '+')]
                            for part in parts:
                                if part == 'A':
                                    approvers.append(col)
                                if part in ('R', 'E'):
                                    responsible.append(col)
                                if part == 'P':
                                    proposers.append(col)
                                if part in ('I', 'I+') and not re.match(r'^cột_\d+$', col.lower()):
                                    informed.append(col)

                        raci_summary = {
                            'approvers': approvers,
                            'responsible': responsible,
                            'proposers': proposers,
                            'informed': informed
                        }
                        scored_matches.append((score, row, raci_summary))
                        _logger.info(
                            "[SQ_DEBUG][ROW]\nrow_idx = %d\nscore = %.2f\nvalues = %s",
                            r_idx, score,
                            json.dumps({c: row.get(c, '') for c in s_cols[:6]}, ensure_ascii=False)
                        )
                        _logger.info(
                            "[SQ_DEBUG][MATCH]\nfilter = LOOKUP('%s')\nscore = %.2f\nmatched = True",
                            lookup_item, score
                        )

                scored_matches.sort(key=lambda x: x[0], reverse=True)
                sheet_matches = [m[1] for m in scored_matches]
                raci_summaries = [m[2] for m in scored_matches]

                _logger.info("[SQ_DEBUG][MATCHED_ROWS]\ncount = %d (sheet '%s')", len(sheet_matches), s_name)
                if sheet_matches:
                    matched_by_sheet[s_name] = {
                        'columns': s_cols,
                        'rows': sheet_matches,
                        'raci_summaries': raci_summaries,
                        'document_name': s.get('document_name'),
                        'top_score': scored_matches[0][0] if scored_matches else 0.0,
                        'has_raci': any(r['approvers'] or r['responsible'] or r['proposers'] for r in raci_summaries)
                    }
                continue

            # Map filter columns to sheet columns with strict boundary checks
            sheet_filters = []
            for flt in filters:
                flt_col = flt.get('column', '')
                norm_flt_col = _normalize_col_name(flt_col)
                matched_col = None
                # Exact match first
                if norm_flt_col in norm_cols_map:
                    matched_col = norm_cols_map[norm_flt_col]
                else:
                    # Word-boundary regex match (prevents matching 'LỚP' into 'ĐỊA PHƯƠNG (để mã lớp)')
                    for nc, actual_c in norm_cols_map.items():
                        if re.search(rf'\b{re.escape(norm_flt_col)}\b', nc):
                            matched_col = actual_c
                            break
                    if not matched_col and len(norm_flt_col) >= 4:
                        for nc, actual_c in norm_cols_map.items():
                            if norm_flt_col in nc or nc in norm_flt_col:
                                matched_col = actual_c
                                break

                if matched_col:
                    sheet_filters.append({
                        'column': matched_col,
                        'operator': str(flt.get('operator') or '=').upper(),
                        'value': str(flt.get('value') or '').strip()
                    })

            if filters and not sheet_filters:
                _logger.info("[SQ_DEBUG][MATCHED_ROWS]\ncount = 0 (no matching filter column in sheet '%s')", s_name)
                continue

            sheet_matches = []
            for r_idx, row in enumerate(s_rows):
                match = True
                for s_flt in sheet_filters:
                    c_name = s_flt['column']
                    op = s_flt['operator']
                    target_val = s_flt['value']
                    row_val = str(row.get(c_name) or '').strip()

                    if op == '=':
                        if _normalize_col_name(row_val) != _normalize_col_name(target_val):
                            match = False
                            break
                    elif op == '!=':
                        if _normalize_col_name(row_val) == _normalize_col_name(target_val):
                            match = False
                            break
                    elif op in ('LIKE', 'ILIKE', 'CONTAINS'):
                        if _normalize_col_name(target_val) not in _normalize_col_name(row_val):
                            match = False
                            break
                    elif op == 'IN':
                        vals_list = [_normalize_col_name(v) for v in target_val.split(',') if v.strip()]
                        if _normalize_col_name(row_val) not in vals_list:
                            match = False
                            break
                    elif op in ('>', '<', '>=', '<='):
                        try:
                            r_num = float(re.sub(r'[^\d.-]', '', row_val))
                            t_num = float(re.sub(r'[^\d.-]', '', target_val))
                            if op == '>' and not (r_num > t_num):
                                match = False; break
                            elif op == '<' and not (r_num < t_num):
                                match = False; break
                            elif op == '>=' and not (r_num >= t_num):
                                match = False; break
                            elif op == '<=' and not (r_num <= t_num):
                                match = False; break
                        except (ValueError, TypeError):
                            if op == '>' and not (row_val > target_val):
                                match = False; break
                            elif op == '<' and not (row_val < target_val):
                                match = False; break
                            elif op == '>=' and not (row_val >= target_val):
                                match = False; break
                            elif op == '<=' and not (row_val <= target_val):
                                match = False; break

                if match:
                    sheet_matches.append(row)
                    _logger.info(
                        "[SQ_DEBUG][ROW]\nrow_idx = %d\nvalues = %s",
                        r_idx,
                        json.dumps({c: row.get(c, '') for c in s_cols[:6]}, ensure_ascii=False)
                    )
                    _logger.info(
                        "[SQ_DEBUG][MATCH]\nfilter = %s\nmatched = True",
                        json.dumps(sheet_filters, ensure_ascii=False)
                    )

            _logger.info("[SQ_DEBUG][MATCHED_ROWS]\ncount = %d (sheet '%s')", len(sheet_matches), s_name)
            if sheet_matches:
                matched_by_sheet[s_name] = {
                    'columns': s_cols,
                    'rows': sheet_matches,
                    'document_name': s.get('document_name')
                }

        # Deterministic sheet selection:
        # If user explicitly specified req_sheet, prioritize it.
        # Otherwise, if multiple sheets matched:
        # 1. Prioritize sheets that have RACI roles assigned on the top matched row
        # 2. Prioritize sheets with refined version ("sửa lại", "final", "chính thức") over drafts
        # 3. Prioritize higher matching top_score
        # 4. Filter out summary sheets ('Tổng', 'TH', 'Total', 'All', 'Summary').
        if req_sheet and req_sheet in matched_by_sheet:
            chosen_sheet_name = req_sheet
        elif len(matched_by_sheet) == 1:
            chosen_sheet_name = list(matched_by_sheet.keys())[0]
        elif len(matched_by_sheet) > 1:
            candidates = list(matched_by_sheet.keys())
            summary_names = ('tổng', 'tong', 'th', 'total', 'all', 'summary')
            non_summary = [sn for sn in candidates if _normalize_col_name(sn) not in summary_names]
            if non_summary:
                candidates = non_summary

            def sheet_priority(sn):
                sdata = matched_by_sheet[sn]
                first_r = sdata['raci_summaries'][0] if sdata.get('raci_summaries') else {}
                named_approvers = [a for a in first_r.get('approvers', []) if not a.isdigit()]
                named_resp = [r for r in first_r.get('responsible', []) if not r.isdigit()]
                named_prop = [p for p in first_r.get('proposers', []) if not p.isdigit()]
                has_top_raci = 1 if (named_approvers or named_resp or named_prop) else 0
                top_score = sdata.get('top_score', 0.0)
                sn_norm = _normalize_col_name(sn)
                is_refined = 1 if any(k in sn_norm for k in ('sua lai', 'final', 'chinh thuc')) else 0
                return (has_top_raci, is_refined, top_score)

            candidates.sort(key=sheet_priority, reverse=True)
            chosen_sheet_name = candidates[0]
        else:
            # Fix: When matched_by_sheet is empty and we have filters, prefer a sheet
            # that actually contains the filter column(s) instead of falling back to the
            # first sheet (which may have numeric-only column headers like 'RAPI ver6-1').
            if filters and target_sheets:
                fallback_candidates = []
                for s in target_sheets:
                    s_cols = s.get('columns', [])
                    norm_cols = {_normalize_col_name(c): c for c in s_cols}
                    # Check if this sheet has ALL filter columns
                    all_found = True
                    for flt in filters:
                        flt_col_norm = _normalize_col_name(flt.get('column', ''))
                        if flt_col_norm not in norm_cols:
                            # Also try word-boundary / substring matching
                            found = any(
                                re.search(rf'\b{re.escape(flt_col_norm)}\b', nc) or
                                (len(flt_col_norm) >= 4 and (flt_col_norm in nc or nc in flt_col_norm))
                                for nc in norm_cols
                            )
                            if not found:
                                all_found = False
                                break
                    if all_found:
                        sn_norm = _normalize_col_name(s['sheet_name'])
                        summary_names = ('tong', 'th', 'total', 'all', 'summary')
                        is_summary = sn_norm in summary_names
                        is_refined = any(k in sn_norm for k in ('sua lai', 'final', 'chinh thuc'))
                        fallback_candidates.append((
                            0 if is_summary else 1,  # non-summary first
                            1 if is_refined else 0,  # refined versions first
                            len(s.get('rows', [])),   # more rows = richer data
                            s['sheet_name']
                        ))
                if fallback_candidates:
                    fallback_candidates.sort(reverse=True)
                    chosen_sheet_name = fallback_candidates[0][3]
                    _logger.info("[SQ_DEBUG][FALLBACK] No rows matched but re-selected sheet '%s' which has matching filter columns", chosen_sheet_name)
                    # Re-run filter matching on the chosen fallback sheet
                    for s in target_sheets:
                        if s['sheet_name'] == chosen_sheet_name:
                            s_cols = s.get('columns', [])
                            s_rows = s.get('rows', [])
                            norm_cols_map = {_normalize_col_name(c): c for c in s_cols}
                            sheet_filters = []
                            for flt in filters:
                                flt_col = flt.get('column', '')
                                norm_flt_col = _normalize_col_name(flt_col)
                                matched_col = norm_cols_map.get(norm_flt_col)
                                if not matched_col:
                                    for nc, actual_c in norm_cols_map.items():
                                        if re.search(rf'\b{re.escape(norm_flt_col)}\b', nc):
                                            matched_col = actual_c
                                            break
                                    if not matched_col and len(norm_flt_col) >= 4:
                                        for nc, actual_c in norm_cols_map.items():
                                            if norm_flt_col in nc or nc in norm_flt_col:
                                                matched_col = actual_c
                                                break
                                if matched_col:
                                    sheet_filters.append({
                                        'column': matched_col,
                                        'operator': str(flt.get('operator') or '=').upper(),
                                        'value': str(flt.get('value') or '').strip()
                                    })
                            # Apply filters
                            sheet_matches = []
                            for row in s_rows:
                                match = True
                                for s_flt in sheet_filters:
                                    c_name = s_flt['column']
                                    op = s_flt['operator']
                                    target_val = s_flt['value']
                                    row_val = str(row.get(c_name) or '').strip()
                                    if op == '=':
                                        if _normalize_col_name(row_val) != _normalize_col_name(target_val):
                                            match = False; break
                                    elif op == '!=':
                                        if _normalize_col_name(row_val) == _normalize_col_name(target_val):
                                            match = False; break
                                    elif op in ('LIKE', 'ILIKE', 'CONTAINS'):
                                        if _normalize_col_name(target_val) not in _normalize_col_name(row_val):
                                            match = False; break
                                    elif op == 'IN':
                                        vals_list = [_normalize_col_name(v) for v in target_val.split(',') if v.strip()]
                                        if _normalize_col_name(row_val) not in vals_list:
                                            match = False; break
                                if match:
                                    sheet_matches.append(row)
                            if sheet_matches:
                                matched_by_sheet[chosen_sheet_name] = {
                                    'columns': s_cols,
                                    'rows': sheet_matches,
                                    'document_name': s.get('document_name')
                                }
                                _logger.info("[SQ_DEBUG][FALLBACK] Recovered %d matched rows from '%s'",
                                             len(sheet_matches), chosen_sheet_name)
                            break
                else:
                    chosen_sheet_name = target_sheets[0]['sheet_name'] if target_sheets else (req_sheet or "Bảng dữ liệu")
            else:
                chosen_sheet_name = target_sheets[0]['sheet_name'] if target_sheets else (req_sheet or "Bảng dữ liệu")

        sheet_name_str = chosen_sheet_name

        first_raci = {}
        if matched_by_sheet and chosen_sheet_name in matched_by_sheet:
            chosen_data = matched_by_sheet[chosen_sheet_name]
            resolved_columns = chosen_data['columns']
            matched_rows = chosen_data['rows']
            if chosen_data.get('raci_summaries'):
                first_raci = chosen_data['raci_summaries'][0]
        else:
            chosen_data = {}
            resolved_columns = target_sheets[0]['columns'] if target_sheets else []
            matched_rows = []

        # 5. Sensitive column filtering & Projection (Section 7 & 9)
        sensitive_keywords = (
            'password', 'mật khẩu', 'mat khau', 'secret', 'token', 'api_key', 'private',
            'sđt', 'so dien thoai', 'số điện thoại', 'phone', 'email', 'mail'
        )
        non_sensitive_cols = [
            c for c in resolved_columns
            if not any(sk in c.lower() for sk in sensitive_keywords)
        ]

        if query_type == 'LOOKUP':
            # For LOOKUP, active columns are:
            # 1. Content columns: TT, STT, Nội dung, Các vấn đề, Lĩnh vực, Phạm vi
            # 2. Identified RACI role columns that have values (A, R, P, I)
            raci_active_cols = first_raci.get('approvers', []) + first_raci.get('responsible', []) + first_raci.get('proposers', []) + first_raci.get('informed', [])
            content_priority = ['stt', 'tt', 'cac van de', 'noi dung', 'linh vuc', 'pham vi', 'hang muc']
            lead_cols = []
            for cp in content_priority:
                for c in resolved_columns:
                    if cp in _normalize_col_name(c) and c not in lead_cols:
                        lead_cols.append(c)
                        break
            lookup_cols = lead_cols + [c for c in raci_active_cols if c not in lead_cols]
            clean_columns = lookup_cols or non_sensitive_cols[:8]
        elif req_select:
            clean_columns = [
                c for c in non_sensitive_cols
                if any(_normalize_col_name(c) == _normalize_col_name(rc) for rc in req_select)
            ] or non_sensitive_cols
        else:
            # Default projection for LIST (Section 7):
            # Prioritize core identity columns: STT, Mã SV/Mã, Họ và, Tên, Lớp, Tài khoản, Ngày sinh, Tên môn...
            core_priority = [
                'stt', 'ma sinh vien', 'ma sv', 'ma so', 'ho va', 'ho va ten', 'ho ten', 'ten',
                'lop', 'tai khoan', 'ngay sinh', 'ten mon', 'mon hoc', 'diem'
            ]
            projected = []
            for cp in core_priority:
                for c in non_sensitive_cols:
                    if _normalize_col_name(c) == cp and c not in projected:
                        projected.append(c)
                        break
            # Append other non-sensitive columns up to 8 columns total
            for c in non_sensitive_cols:
                if c not in projected:
                    if len(projected) < 8:
                        projected.append(c)
            clean_columns = projected or non_sensitive_cols

        # 6. Apply Result Semantics (Section 21)
        if query_type == 'COUNT':
            total_count = len(matched_rows)
            result_count = 1
            returned_count = 1
            truncated = False
            final_columns = ['TỔNG SỐ']
            final_rows = [{'TỔNG SỐ': total_count}]
        elif query_type in ('SUM', 'AVG') and aggregate:
            agg_col = aggregate.get('column')
            total_matches = len(matched_rows)
            vals = []
            if agg_col and agg_col != '*':
                for r in matched_rows:
                    try:
                        vals.append(float(re.sub(r'[^\d.-]', '', str(r.get(agg_col) or '0'))))
                    except ValueError:
                        pass
            agg_val = sum(vals) if query_type == 'SUM' else (sum(vals) / max(len(vals), 1))
            result_count = 1
            returned_count = 1
            truncated = False
            final_columns = [f"{query_type} ({agg_col or 'GIÁ TRỊ'})"]
            final_rows = [{final_columns[0]: agg_val}]
        else:
            # LIST or LOOKUP query
            result_count = len(matched_rows)
            returned_rows = matched_rows[:max_limit]
            returned_count = len(returned_rows)
            truncated = (result_count > returned_count)
            final_columns = clean_columns
            final_rows = [
                {col: r.get(col, '') for col in clean_columns}
                for r in returned_rows
            ]

        exec_time = int((time.time() - start_time) * 1000)

        # Observability logging (Section 3 & 11)
        _logger.info(
            "[SQ_DEBUG][RESULT]\nprojected_columns = %s\nreturned_count = %d",
            json.dumps(final_columns, ensure_ascii=False), returned_count
        )
        _logger.info("[STRUCTURED_QUERY] result_count=%d", result_count)
        _logger.info("[STRUCTURED_QUERY] returned_count=%d", returned_count)
        _logger.info("[STRUCTURED_QUERY] truncated=%s", truncated)
        _logger.info("[STRUCTURED_QUERY] execution_ms=%d", exec_time)
        _logger.info("[STRUCTURED_QUERY] success=True")

        return {
            'query_type': query_type,
            'sheet': sheet_name_str,
            'filters': filters,
            'lookup_item': lookup_item,
            'target_action': target_action,
            'raci_summary': first_raci if query_type == 'LOOKUP' else None,
            'result_count': result_count,
            'returned_count': returned_count,
            'truncated': truncated,
            'columns': final_columns,
            'rows': final_rows,
            'execution_time_ms': exec_time,
            'success': True,
            'notice': f"Truy vấn bảng an toàn: tìm thấy {result_count} bản ghi khớp."
        }

    except Exception as e:
        exec_time = int((time.time() - start_time) * 1000)
        _logger.error("[STRUCTURED_QUERY_ERROR] %s (execution_ms=%d)", str(e), exec_time)
        return {
            'query_type': 'STRUCTURED_DATA',
            'error': str(e),
            'success': False,
            'result_count': 0,
            'returned_count': 0,
            'truncated': False,
            'columns': [],
            'rows': [],
            'execution_time_ms': exec_time
        }


