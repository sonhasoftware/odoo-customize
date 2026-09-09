# -*- coding: utf-8 -*-
import json
import logging
import re
import requests
from odoo.http import request
from ..utils.security_utils import normalize_model_name
from .sql_engine import _normalize_col_name

_logger = logging.getLogger(__name__)


def classify_route_with_reason(message, topic=None, env=None):
    """Classify query intent into SEMANTIC_RAG, SCHEMA_METADATA, or STRUCTURED_DATA with detailed reason."""
    msg = (message or '').lower().strip()

    # 1. SCHEMA_METADATA keywords
    schema_keywords = (
        'cột nào', 'mấy cột', 'bao nhiêu cột', 'danh sách cột', 'cấu trúc',
        'schema', 'nói về gì', 'nói về cái gì', 'nội dung file', 'gồm những sheet nào',
        'mấy sheet', 'tổng quan file', 'chứa thông tin gì', 'tóm tắt bảng', 'tóm tắt file'
    )
    if any(kw in msg for kw in schema_keywords):
        return 'SCHEMA_METADATA', "Tra cứu cấu trúc schema, cột hoặc danh sách sheet"

    # 2. STRUCTURED_DATA: Table / RACI Matrix / Authority / Responsibility Lookup patterns
    lookup_keywords = (
        'ai phê duyệt', 'ai phe duyet', 'những ai phê duyệt', 'nhung ai phe duyet', 'ai duyệt', 'ai duyet',
        'ai ký', 'ai ky', 'ai thẩm tra', 'ai tham tra', 'ai soát xét', 'ai soat xet',
        'ai chịu trách nhiệm', 'ai chiu trach nhiem', 'những ai chịu trách nhiệm', 'ai thực hiện', 'ai thuc hien',
        'ai đề xuất', 'ai de xuat', 'ai trình duyệt', 'ai trinh duyet', 'ai phụ trách', 'ai phu trach',
        'ai có quyền', 'ai co quyen', 'quyền này thuộc về ai', 'quyen nay thuoc ve ai', 'quyền phê duyệt', 'quyen phe duyet',
        'thẩm quyền phê duyệt', 'thẩm quyền thuộc về', 'thuộc về ai', 'thuoc ve ai', 'phân cho ai', 'phan cho ai',
        'giao cho ai', 'giao cho đơn vị nào', 'đơn vị nào phụ trách', 'don vi nao phu trach',
        'bộ phận nào phụ trách', 'phòng ban nào phụ trách', 'vai trò nào', 'vai tro nao',
        'nội dung nào có', 'các nội dung nào có', 'hạng mục nào có'
    )
    if any(kw in msg for kw in lookup_keywords):
        return 'STRUCTURED_DATA', "Phát hiện câu hỏi tra cứu phân quyền, thẩm quyền hoặc tra cứu dòng trong bảng (LOOKUP)"

    # 2b. Explicit condition pattern (e.g. "CT = A", "LỚP = CHDN421", "TRẠNG THÁI = ĐANG HOẠT ĐỘNG")
    if re.search(r'\b[A-Za-z0-9_À-ỹĐđ\s]{1,25}\s*(=|!=|>=|<=|>|<|\bIN\b)\s*[A-Za-z0-9_À-ỹĐđ]+', msg):
        return 'STRUCTURED_DATA', "Phát hiện biểu thức lọc điều kiện bảng có cấu trúc (FILTER/LIST)"

    # 2c. Quantitative / Aggregation / List keywords
    #     NOTE: Only ACTION/OPERATOR keywords here. Subject nouns like 'chi phí', 'doanh thu',
    #     'lương' were removed because they cause false-positive routing for semantic/procedural
    #     questions (e.g. "quy trình thanh toán chi phí tiếp khách" is SEMANTIC, not STRUCTURED).
    structured_keywords = (
        'tổng', 'tong', 'bao nhiêu', 'bao nhieu', 'đếm', 'dem', 'tính tổng', 'tinh tong', 'trung bình',
        'lớn nhất', 'nhỏ nhất', 'cao nhất', 'thấp nhất', 'liệt kê', 'liet ke', 'danh sách', 'danh sach',
        'lọc', 'loc', 'tháng nào', 'năm nào',
        'hơn', 'kém', 'top 5', 'top 10', 'sum', 'count', 'avg', 'min', 'max'
    )
    if any(kw in msg for kw in structured_keywords):
        return 'STRUCTURED_DATA', "Phát hiện câu hỏi định lượng, đếm số lượng, tổng hợp hoặc lọc danh sách (AGGREGATION/LIST)"

    return 'SEMANTIC_RAG', "Câu hỏi tra cứu nội dung tri thức, quy trình hoặc tài liệu văn bản phi cấu trúc (SEMANTIC_RAG)"


def classify_route_type(message, topic=None, env=None):
    """Heuristic fallback to classify query intent into SEMANTIC_RAG, SCHEMA_METADATA, or STRUCTURED_DATA."""
    route_type, _ = classify_route_with_reason(message, topic=topic, env=env)
    return route_type


def parse_to_structured_query_object(query_text, schema_info=None):
    """Parse natural language query or structured query string into a normalized
    Structured Query Object representation (Section 20).
    
    Supports: LIST, COUNT, SUM, AVG, MIN, MAX, LOOKUP, FILTER.
    Returns:
        dict: Structured Query Object with query_type, sheet, filters, select, order_by, limit, aggregate, lookup_item, target_action.
    """
    if isinstance(query_text, dict):
        q_type = str(query_text.get('query_type') or 'LIST').upper()
        if q_type not in ('LIST', 'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'LOOKUP', 'FILTER'):
            q_type = 'LIST'
        return {
            'query_type': q_type,
            'sheet': query_text.get('sheet'),
            'filters': query_text.get('filters') or [],
            'select': query_text.get('select') or [],
            'order_by': query_text.get('order_by') or [],
            'limit': query_text.get('limit'),
            'aggregate': query_text.get('aggregate'),
            'lookup_item': query_text.get('lookup_item'),
            'target_action': query_text.get('target_action')
        }

    raw = str(query_text or '').strip()
    raw_lower = raw.lower()

    # 1. Determine query_type, target_action, lookup_item
    query_type = 'LIST'
    aggregate = None
    target_action = None
    lookup_item = None

    lookup_approval_kw = ('ai phê duyệt', 'ai phe duyet', 'những ai phê duyệt', 'nhung ai phe duyet', 'ai duyệt', 'ai duyet', 'ai ký', 'ai ky', 'quyền phê duyệt', 'quyen phe duyet', 'thẩm quyền phê duyệt')
    lookup_resp_kw = ('ai chịu trách nhiệm', 'ai chiu trach nhiem', 'những ai chịu trách nhiệm', 'ai thẩm tra', 'ai tham tra', 'ai soát xét', 'ai soat xet', 'ai thực hiện', 'ai thuc hien')
    lookup_propose_kw = ('ai đề xuất', 'ai de xuat', 'ai trình duyệt', 'ai trinh duyet', 'ai lập', 'ai lap')
    lookup_general_kw = ('thuộc về ai', 'thuoc ve ai', 'phân cho ai', 'phan cho ai', 'giao cho ai', 'ai có quyền', 'ai co quyen', 'đơn vị nào phụ trách', 'vai trò nào')

    if any(kw in raw_lower for kw in lookup_approval_kw):
        query_type = 'LOOKUP'
        target_action = 'A'
    elif any(kw in raw_lower for kw in lookup_resp_kw):
        query_type = 'LOOKUP'
        target_action = 'R'
    elif any(kw in raw_lower for kw in lookup_propose_kw):
        query_type = 'LOOKUP'
        target_action = 'P'
    elif any(kw in raw_lower for kw in lookup_general_kw):
        query_type = 'LOOKUP'
        target_action = 'A'
    else:
        count_keywords = ('bao nhiêu', 'bao nhieu', 'đếm', 'dem', 'count', 'tổng số sinh viên', 'tổng số nhân viên')
        sum_keywords = ('tổng tiền', 'tong tien', 'tổng chi phí', 'tong chi phi', 'tổng doanh thu', 'tong doanh thu', 'tổng lương', 'tong luong')
        avg_keywords = ('trung bình', 'trung binh', 'bình quân', 'binh quan', 'avg', 'average')
        if any(kw in raw_lower for kw in count_keywords):
            query_type = 'COUNT'
            aggregate = {'function': 'COUNT', 'column': '*'}
        elif any(kw in raw_lower for kw in sum_keywords):
            query_type = 'SUM'
            aggregate = {'function': 'SUM', 'column': '*'}
        elif any(kw in raw_lower for kw in avg_keywords):
            query_type = 'AVG'
            aggregate = {'function': 'AVG', 'column': '*'}

    # If LOOKUP, extract lookup_item from natural question
    if query_type == 'LOOKUP':
        cleaned_item = raw
        triggers = [
            r'^(?:ai\s+phê\s+duyệt|ai\s+phe\s+duyet|những\s+ai\s+phê\s+duyệt|ai\s+duyệt|ai\s+ký|ai\s+chịu\s+trách\s+nhiệm|ai\s+thẩm\s+tra|ai\s+soát\s+xét|ai\s+thực\s+hiện|ai\s+đề\s+xuất|ai\s+trình\s+duyệt|ai\s+có\s+quyền|quyền\s+phê\s+duyệt|đơn\s+vị\s+nào\s+phụ\s+trách)\s+(?:đối\s+với|về|cho)?\s*',
            r'\s*(?:thuộc\s+về\s+ai|được\s+phân\s+cho\s+ai|giao\s+cho\s+ai|do\s+ai\s+phụ\s+trách)\s*\??$'
        ]
        for tr in triggers:
            cleaned_item = re.sub(tr, '', cleaned_item, flags=re.IGNORECASE).strip()
        cleaned_item = cleaned_item.rstrip('?.,;!').strip()
        lookup_item = cleaned_item or raw

    # 2. Extract sheet if explicitly specified (e.g., "sheet IT05", "bảng Ver6-draf", "sheet final")
    sheet_match = re.search(
        r'\b(?:sheet|bảng|bang)\s+([A-Za-z0-9_À-ỹĐđ\-]+(?:\s+[A-Za-z0-9_À-ỹĐđ\-]+)*?)(?=\s+(?:có|trong|ở|tại|theo|thuộc|gồm|chứa|là|\?|$)|$|\?|,)',
        raw, re.IGNORECASE
    )
    raw_sheet = sheet_match.group(1).strip() if sheet_match else None
    sheet = None
    if raw_sheet:
        norm_s = _normalize_col_name(raw_sheet)
        GENERIC_SHEET_TERMS = {'phan quyen', 'phan', 'quyen', 'tinh', 'du lieu', 'diem', 'luong', 'ke', 'raci', 'nay', 'do', 'tren', 'duoi', 'danh sach'}
        if norm_s not in GENERIC_SHEET_TERMS and not any(gt in norm_s for gt in ('phan quyen', 'du lieu', 'danh sach', 'tong hop')):
            sheet = raw_sheet

    # Fix: Strip sheet reference from lookup_item to prevent token pollution
    # e.g. "kế hoạch kinh doanh trong sheet final" → "kế hoạch kinh doanh"
    if query_type == 'LOOKUP' and lookup_item and sheet:
        lookup_item = re.sub(
            r'\s*(?:trong|ở|tại|theo|trên|của)?\s*(?:sheet|bảng|bang)\s+' + re.escape(sheet) + r'\s*',
            '', lookup_item, flags=re.IGNORECASE
        ).strip().rstrip('?.,;!').strip()
        if not lookup_item:
            lookup_item = raw

    # 3. Extract filters
    filters = []

    # Check for explicit assignments like "CT = A" or "LỚP = CHDN421" or "các nội dung nào có CT = A"
    explicit_matches = re.findall(
        r'([A-Za-z0-9_À-ỹĐđ\s]{1,25}?)\s*(=|!=|>=|<=|>|<|\bILIKE\b|\bLIKE\b|\bIN\b)\s*[\'"]?([^\'"\n,;?]+?)[\'"]?(?:\s+AND|\s*$|,|\?)',
        raw,
        re.IGNORECASE
    )
    if explicit_matches:
        for col_cand, op, val in explicit_matches:
            col_clean = col_cand.strip().strip("'\"")
            val_clean = val.strip().strip("'\"")
            # Strip trailing prepositional context like "trong bảng phân quyền", "tại sheet X", etc.
            val_clean = re.sub(r'\s+(?:trong|ở|tại|theo|thuộc|của)\s+.*$', '', val_clean, flags=re.IGNORECASE).strip()
            col_clean = re.sub(r'^(?:các\s+nội\s+dung\s+nào\s+có|nội\s+dung\s+nào\s+có|hạng\s+mục\s+nào\s+có|danh\s+sách|cho\s+tôi\s+biết|tìm)\s+', '', col_clean, flags=re.IGNORECASE).strip()
            stop_words = ('select', 'from', 'where', 'and', 'or', 'danh sách', 'liệt kê', 'cho tôi', 'tìm')
            if col_clean.lower() not in stop_words and len(col_clean) >= 1 and val_clean:
                filters.append({
                    'column': col_clean.upper(),
                    'operator': op.strip().upper(),
                    'value': val_clean
                })

    # Pattern A: Vietnamese domain heuristics (e.g. "lớp CHDN421", "mã sinh viên SV001")
    if not filters and query_type != 'LOOKUP':
        class_match = re.search(r'\b(?:lớp|lop)\b.*?\b([A-Za-z0-9]*\d[A-Za-z0-9_\-]*)\b', raw, re.IGNORECASE)
        if not class_match:
            class_match = re.search(r'\b(?:lớp|lop)\s+([A-Za-z0-9_\-]+)', raw, re.IGNORECASE)
        if class_match:
            filters.append({
                'column': 'LỚP',
                'operator': '=',
                'value': class_match.group(1).upper()
            })

        code_match = re.search(r'\b(?:mã\s+sinh\s+viên|ma\s+sinh\s+vien|mã\s+sv|ma\s+sv|mã\s+nv|ma\s+nv|mã\s+nhân\s+viên)\s+([A-Za-z0-9_\-]+)', raw, re.IGNORECASE)
        if code_match:
            filters.append({
                'column': 'MÃ SINH VIÊN',
                'operator': '=',
                'value': code_match.group(1).upper()
            })

        dept_match = re.search(r'\b(?:phòng\s+ban|phòng|bộ\s+phận)\s+([A-Za-zÀ-ỹĐđ0-9_\s]+?)(?:\s+(?:làm|ở|có|được|thuộc)|$)', raw, re.IGNORECASE)
        if dept_match:
            dept_val = dept_match.group(1).strip()
            if dept_val and len(dept_val) >= 2:
                filters.append({
                    'column': 'PHÒNG BAN',
                    'operator': '=',
                    'value': dept_val
                })

        status_match = re.search(r'\b(?:trạng\s+thái|tình\s+trạng)\s+([A-Za-zÀ-ỹĐđ0-9_\s]+?)(?:\s+(?:của|ở|có)|$)', raw, re.IGNORECASE)
        if status_match:
            status_val = status_match.group(1).strip()
            if status_val and len(status_val) >= 2:
                filters.append({
                    'column': 'TRẠNG THÁI',
                    'operator': '=',
                    'value': status_val
                })

    # Pattern C: Check against schema_info if provided
    if schema_info and isinstance(schema_info, dict):
        val_map = schema_info.get('values_map', {})
        if not filters and val_map:
            for col_name, known_vals in val_map.items():
                for kv in known_vals:
                    if str(kv).lower() in raw_lower and len(str(kv)) >= 2:
                        filters.append({
                            'column': col_name,
                            'operator': '=',
                            'value': str(kv)
                        })
                        break
                if filters:
                    break

    return {
        'query_type': query_type,
        'sheet': sheet,
        'filters': filters,
        'select': [],
        'order_by': [],
        'limit': None,
        'aggregate': aggregate,
        'lookup_item': lookup_item,
        'target_action': target_action
    }


def rewrite_search_query(env, message, conversation_id, api_key, model):
    """Rewrite user message into a standalone query, detect relevance (is_valid),
    extract metadata filters (doc_type, department, apply_year), route query intent (route_type),
    extract structured_query for structured tabular data queries, and provide route_reason."""
    default_filters = {}
    default_route, default_reason = classify_route_with_reason(message)
    default_structured_query = parse_to_structured_query_object(message) if default_route == 'STRUCTURED_DATA' else None
    if env is None:
        try:
            env = request.env
        except Exception:
            return message, default_filters, True, default_route, default_structured_query, default_reason

    try:
        db_messages = env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation_id)
        ], order='create_date desc', limit=6)

        history_lines = []
        if len(db_messages) > 1:
            for m in reversed(db_messages[1:]):
                role_str = "Người dùng" if m.role == 'user' else "Trợ lý AI"
                history_lines.append(f"{role_str}: {m.content}")
        history_text = "\n".join(history_lines) if history_lines else "(Không có lịch sử trước đó)"

        if not api_key:
            return message, default_filters, True, default_route, default_structured_query, default_reason

        rewrite_prompt = (
            "Bạn là bộ phận phân loại và định tuyến câu truy vấn cho hệ thống AI doanh nghiệp.\n"
            "Nhiệm vụ: Phân tích nội dung người dùng gửi và lịch sử hội thoại để:\n"
            "1. Đánh giá tính hợp lệ ('is_valid'):\n"
            "   - Đặt là FALSE nếu nội dung người dùng là: đoạn văn bản ngẫu nhiên copy trên mạng, lời bài hát, "
            "thơ ca, tin tức báo chí ngoài lề, spam, chuỗi ký tự ngẫu nhiên hoặc nội dung không chứa câu hỏi/yêu cầu nghiệp vụ nào.\n"
            "   - Đặt là TRUE nếu là câu hỏi nghiệp vụ, yêu cầu tra cứu, chào hỏi, hoặc giao tiếp thông thường.\n"
            "2. Nếu 'is_valid' = TRUE: Viết lại câu hỏi thành câu độc lập ('query') đầy đủ thông tin (tên, mốc thời gian, điều kiện lọc).\n"
            "   NẾU 'is_valid' = FALSE: TUYỆT ĐỐI KHÔNG tự gán ghép với ngữ cảnh lịch sử cũ, gán 'query' = null.\n"
            "3. Trích xuất metadata bộ lọc ('filters') nếu người dùng có chỉ định rõ ràng:\n"
            "   - 'apply_year': Số nguyên (ví dụ: 2024, 2023) hoặc null nếu không nhắc đến năm.\n"
            "   - 'doc_type': Một trong các giá trị ['regulation', 'process', 'report', 'form', 'manual'] hoặc null.\n"
            "   - 'department': Tên phòng ban ngắn gọn (ví dụ: 'Kế toán', 'Nhân sự', 'IT') hoặc null.\n"
            "4. Phân loại định tuyến ý định ('route_type'):\n"
            "   - 'SCHEMA_METADATA': Hỏi về cấu trúc file, các cột, danh sách sheet, hoặc hỏi file này nói về cái gì.\n"
            "   - 'STRUCTURED_DATA': Khi câu hỏi có thể trả lời bằng cách tra cứu hoặc lọc dữ liệu trong bảng/ma trận dữ liệu có cấu trúc:\n"
            "       + Định lượng, đếm số lượng, tính tổng, trung bình, so sánh số liệu, lọc danh sách (FILTER, LIST, COUNT, SUM, AVG).\n"
            "       + Tra cứu bảng/ma trận phân quyền, phân vai, trách nhiệm (LOOKUP): 'Ai phê duyệt...', 'Ai chịu trách nhiệm...', 'Ai thực hiện...', 'Ai đề xuất...', 'Đơn vị/vai trò nào phụ trách...', 'Quyền này thuộc về ai...', 'Nội dung nào được phân cho ai...', 'Ai có quyền...', 'nội dung nào có CT = A'.\n"
            "   - 'SEMANTIC_RAG': Hỏi định tính, tra cứu quy định văn bản, quy trình tự luận, mô tả, nội dung tài liệu văn bản chung.\n"
            "5. Nếu là 'STRUCTURED_DATA', hãy tạo đối tượng cấu trúc ('structured_query') có dạng:\n"
            "   - Nếu hỏi tra cứu quyền/vai trò/dòng: {\"query_type\": \"LOOKUP\", \"lookup_item\": \"tên nội dung/nghiệp vụ cần tìm\", \"target_action\": \"A (phê duyệt) hoặc R (trách nhiệm/soát xét) hoặc P (đề xuất) hoặc I (thông báo)\", \"filters\": []}\n"
            "   - Nếu hỏi danh sách hoặc lọc hoặc đếm: {\"query_type\": \"LIST hoặc COUNT\", \"sheet\": null, \"filters\": [{\"column\": \"Tên_Cột\", \"operator\": \"=\", \"value\": \"Giá_Trị\"}]}\n\n"
            f"Lịch sử hội thoại:\n{history_text}\n\n"
            f"Nội dung người dùng gửi:\n{message}\n\n"
            "Trả về định dạng JSON thuần túy (không markdown block, không giải thích gì thêm):\n"
            '{"is_valid": true, "query": "câu truy vấn độc lập", "filters": {"apply_year": null, "doc_type": null, "department": null}, "route_type": "SEMANTIC_RAG", "route_reason": "lý do định tuyến", "structured_query": null}'
        )

        clean_model = normalize_model_name(model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': rewrite_prompt}]}],
            'generationConfig': {'maxOutputTokens': 250, 'temperature': 0.1}
        }

        res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get('candidates', [])
            if candidates and 'content' in candidates[0]:
                parts = candidates[0]['content'].get('parts', [])
                if parts and 'text' in parts[0]:
                    raw_text = parts[0]['text'].strip()
                    if raw_text.startswith('```'):
                        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                        raw_text = re.sub(r'\s*```$', '', raw_text)
                    try:
                        parsed = json.loads(raw_text)
                        is_valid = parsed.get('is_valid', True)
                        if not is_valid:
                            _logger.info("[REWRITE_GUARD] Detected off-topic/nonsense/copied input: '%s...'", message[:80].replace('\n', ' '))
                            return message, default_filters, False, default_route, None, default_reason

                        query = parsed.get('query') or message
                        filters = parsed.get('filters') or {}
                        clean_filters = {}
                        if filters.get('apply_year'):
                            try:
                                clean_filters['apply_year'] = int(filters['apply_year'])
                            except (ValueError, TypeError):
                                pass
                        if filters.get('doc_type') in ('regulation', 'process', 'report', 'form', 'manual', 'other'):
                            clean_filters['doc_type'] = filters['doc_type']
                        if filters.get('department') and isinstance(filters['department'], str) and len(filters['department'].strip()) >= 2:
                            clean_filters['department'] = filters['department'].strip()

                        route_type = parsed.get('route_type')
                        route_reason = parsed.get('route_reason')

                        # Heuristic intent check & validation
                        h_route, h_reason = classify_route_with_reason(query)
                        if h_route == 'STRUCTURED_DATA':
                            route_type = 'STRUCTURED_DATA'
                            route_reason = h_reason
                        elif route_type not in ('SEMANTIC_RAG', 'SCHEMA_METADATA', 'STRUCTURED_DATA'):
                            route_type, route_reason = h_route, h_reason

                        if not route_reason:
                            route_reason = h_reason

                        raw_sq = parsed.get('structured_query')
                        if route_type == 'STRUCTURED_DATA':
                            structured_query = parse_to_structured_query_object(raw_sq or query)
                        else:
                            structured_query = None

                        _logger.info("Rewrote query: '%s' -> '%s' (Route: %s [%s], Filters: %s, is_valid: %s, StructuredQuery: %s)", message, query, route_type, route_reason, clean_filters, is_valid, structured_query)
                        _logger.info(
                            "[RAG_DEBUG][QUERY]\n"
                            "  - original_query: '%s'\n"
                            "  - rewritten_query: '%s'\n"
                            "  - route_type: %s\n"
                            "  - route_reason: %s\n"
                            "  - structured_query: %s\n"
                            "  - is_valid: %s\n"
                            "  - conversation_id: %s\n"
                            "  - metadata_filters: %s",
                            message, query, route_type, route_reason, json.dumps(structured_query, ensure_ascii=False) if structured_query else 'null', is_valid, conversation_id, json.dumps(clean_filters, ensure_ascii=False)
                        )
                        return query, clean_filters, True, route_type, structured_query, route_reason
                    except json.JSONDecodeError:
                        h_route, h_reason = classify_route_with_reason(raw_text)
                        structured_query = parse_to_structured_query_object(raw_text) if h_route == 'STRUCTURED_DATA' else None
                        _logger.info("Rewrote query (text fallback): '%s' -> '%s' (Route: %s [%s])", message, raw_text, h_route, h_reason)
                        _logger.info(
                            "[RAG_DEBUG][QUERY]\n"
                            "  - original_query: '%s'\n"
                            "  - rewritten_query: '%s'\n"
                            "  - route_type: %s\n"
                            "  - route_reason: %s\n"
                            "  - structured_query: %s\n"
                            "  - is_valid: True (fallback)\n"
                            "  - conversation_id: %s\n"
                            "  - metadata_filters: %s",
                            message, raw_text, h_route, h_reason, json.dumps(structured_query, ensure_ascii=False) if structured_query else 'null', conversation_id, json.dumps(default_filters, ensure_ascii=False)
                        )
                        return raw_text, default_filters, True, h_route, structured_query, h_reason
    except Exception as e:
        _logger.warning("Failed to rewrite query: %s", str(e))

    h_route, h_reason = classify_route_with_reason(message)
    structured_query = parse_to_structured_query_object(message) if h_route == 'STRUCTURED_DATA' else None
    _logger.info(
        "[RAG_DEBUG][QUERY]\n"
        "  - original_query: '%s'\n"
        "  - rewritten_query: '%s'\n"
        "  - route_type: %s\n"
        "  - route_reason: %s\n"
        "  - structured_query: %s\n"
        "  - is_valid: True (default)\n"
        "  - conversation_id: %s\n"
        "  - metadata_filters: %s",
        message, message, h_route, h_reason, json.dumps(structured_query, ensure_ascii=False) if structured_query else 'null', conversation_id, json.dumps(default_filters, ensure_ascii=False)
    )
    return message, default_filters, True, h_route, structured_query, h_reason


def should_use_hyde(message):
    """Selectively determine if HyDE should be activated based on abstract reasoning keywords."""
    if not message or len(message.strip()) < 10:
        return False
    abstract_indicators = [
        'tại sao', 'vì sao', 'nguyên nhân', 'giải thích', 'lý do',
        'so sánh', 'khác nhau', 'giống nhau', 'phân biệt',
        'ảnh hưởng', 'tác động', 'phân tích', 'đánh giá', 'nhận xét',
        'ưu điểm', 'nhược điểm', 'ưu nhược điểm', 'như thế nào',
        'cơ chế', 'bản chất', 'nguyên tắc',
        'why', 'explain', 'compare', 'difference between', 'how does'
    ]
    msg_lower = message.lower()
    return any(ind in msg_lower for ind in abstract_indicators)


def generate_hypothetical_document(env, query, api_key, model=None):
    """Generate a short hypothetical document passage that directly answers the abstract query."""
    if not query or not api_key:
        return None
    if env is None:
        try:
            env = request.env
        except Exception:
            return None

    try:
        params = env['ir.config_parameter'].sudo()
        target_model = normalize_model_name(model or params.get_param('topic_chatbot.gemini_model', default='gemini-3.6-flash'))
        prompt = (
            "Hãy đóng vai chuyên gia tài liệu doanh nghiệp. Hãy viết một đoạn văn mẫu ngắn 2-3 câu "
            "(như một đoạn trích trong sổ tay quy định / tài liệu nội bộ) giải thích và trả lời trực tiếp cho câu hỏi sau.\n"
            "Chỉ viết đoạn văn giả định, không mở bài hay giải thích thêm.\n\n"
            f"Câu hỏi: {query}\n\n"
            "Đoạn văn giả định:"
        )
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
            'generationConfig': {'maxOutputTokens': 120, 'temperature': 0.3}
        }
        res = requests.post(url, headers={'Content-Type': 'application/json'}, json=payload, timeout=8)
        if res.status_code == 200:
            data = res.json()
            candidates = data.get('candidates', [])
            if candidates and 'content' in candidates[0]:
                parts = candidates[0]['content'].get('parts', [])
                if parts and 'text' in parts[0]:
                    return parts[0]['text'].strip()
    except Exception as e:
        _logger.debug("HyDE hypothetical generation skipped: %s", str(e))
    return None
