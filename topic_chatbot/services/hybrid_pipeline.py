# -*- coding: utf-8 -*-
"""Verified hand-off helpers for the Ollama -> Gemini chat pipeline."""

import json

from .diagram_service import DiagramSpecError


QUERY_TOOL_NAMES = frozenset(('query_odoo_data', 'query_sql_server_data'))


def query_tools_only(tools_list):
    """Return declarations that may read data but can never render output."""
    return [tool for tool in (tools_list or []) if tool.get('name') in QUERY_TOOL_NAMES]


def collect_query_context(events):
    """Normalize raw tool results while retaining the source and truncation flag."""
    batches = []
    truncated = False
    total_records = 0
    seen_batches = set()
    for event in events or []:
        if event.get('name') not in QUERY_TOOL_NAMES:
            continue
        result = event.get('result')
        if isinstance(result, dict):
            records = result.get('data') if isinstance(result.get('data'), list) else []
            batch_truncated = bool(result.get('truncated'))
            error = result.get('error')
        elif isinstance(result, list):
            records = result
            batch_truncated = False
            error = None
        else:
            records = []
            batch_truncated = False
            error = 'Kết quả truy vấn không hợp lệ.'

        args = event.get('args') or {}
        source = args.get('model') or ('sql_server' if event.get('name') == 'query_sql_server_data' else '')
        signature = json.dumps(
            {'source': source, 'query': args.get('domain') or args.get('sql_query') or '', 'records': records},
            ensure_ascii=False,
            default=str,
            sort_keys=True,
        )
        if signature in seen_batches:
            truncated = truncated or batch_truncated
            continue
        seen_batches.add(signature)
        batches.append({
            'source': source,
            'query': args.get('domain') or args.get('sql_query') or '',
            'records': records,
            'truncated': batch_truncated,
            'error': error,
        })
        total_records += len(records)
        truncated = truncated or batch_truncated

    return {
        'batches': batches,
        'truncated': truncated,
        'record_count': total_records,
    }


def build_gemini_handoff_prompt(ollama_summary, query_context):
    """Create one explicit, auditable prompt from Ollama output and verified rows."""
    query_context = query_context or {'batches': [], 'truncated': False, 'record_count': 0}
    packet = {
        'ollama_summary': str(ollama_summary or '').strip(),
        'database_result': query_context,
    }
    payload = json.dumps(packet, ensure_ascii=False, default=str, separators=(',', ':'))
    if not query_context.get('batches'):
        return (
            "DỮ LIỆU BÀN GIAO TỪ PIPELINE OLLAMA → GEMINI\n"
            "Không có truy vấn database trong lượt này. Hãy dùng chỉ dẫn hệ thống, ngữ cảnh tài liệu gốc "
            "và bản tóm tắt Ollama dưới đây để trả lời; không được coi bản tóm tắt là nguồn mới.\n"
            f"GÓI BÀN GIAO:\n{payload}"
        )
    return (
        "DỮ LIỆU BÀN GIAO TỪ PIPELINE OLLAMA → GEMINI\n"
        "Dữ liệu trong database_result do máy chủ lấy trực tiếp và là nguồn kiểm chứng cuối cùng. "
        "ollama_summary chỉ là bản tóm tắt hỗ trợ, không được dùng để ghi đè hoặc bổ sung dữ liệu.\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Chỉ trả lời bằng dữ liệu có trong database_result.records; không tự thêm người, chức danh, phòng ban hoặc quan hệ.\n"
        "2. Khi tạo sơ đồ, id của mỗi node phải đúng bằng chuỗi id của bản ghi database.\n"
        "3. Với sơ đồ tổ chức nhân viên, cạnh chỉ đi từ parent_id_record_id đến id nhân viên.\n"
        "4. Nếu database_result.truncated=true, không được tạo sơ đồ toàn bộ hoặc kết luận dữ liệu là đầy đủ; "
        "hãy yêu cầu người dùng thu hẹp theo công ty, phòng ban hoặc quản lý.\n"
        "5. Nếu không có bản ghi, phải nói rõ không tìm thấy dữ liệu.\n"
        f"GÓI DỮ LIỆU ĐÃ XÁC MINH:\n{payload}"
    )


def _records_by_id(query_context):
    records = {}
    sources = {}
    for batch in (query_context or {}).get('batches', []):
        source = batch.get('source') or ''
        for record in batch.get('records') or []:
            if not isinstance(record, dict) or record.get('id') in (None, False, ''):
                continue
            record_id = str(record['id'])
            if record_id in records and records[record_id] != record:
                raise DiagramSpecError(
                    'Có nhiều nguồn dữ liệu dùng cùng một ID. Vui lòng thu hẹp phạm vi sơ đồ.'
                )
            records[record_id] = record
            sources[record_id] = source
    return records, sources


def validate_and_normalize_diagram(spec, query_context):
    """Reject invented nodes and rebuild employee labels/edges from verified rows."""
    if (query_context or {}).get('truncated'):
        raise DiagramSpecError(
            'Kết quả database đang bị cắt bớt. Hãy thu hẹp theo công ty, phòng ban hoặc quản lý trước khi tạo sơ đồ.'
        )

    records, sources = _records_by_id(query_context)
    if not records:
        raise DiagramSpecError('Chưa có dữ liệu database đã xác minh để tạo sơ đồ.')
    if not isinstance(spec, dict):
        raise DiagramSpecError('Đặc tả sơ đồ không hợp lệ.')

    normalized = dict(spec)
    diagram_type = str(normalized.get('diagram_type') or 'flowchart').strip().lower()
    nodes = []
    selected_ids = set()
    selected_records = {}
    for raw_node in normalized.get('nodes') or []:
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get('id') or '').strip()
        record = records.get(node_id)
        if not record:
            raise DiagramSpecError(
                f'Node "{node_id or "(trống)"}" không tồn tại trong kết quả database đã xác minh.'
            )
        node = dict(raw_node)
        node['id'] = node_id
        if sources.get(node_id) == 'employees':
            node['label'] = str(record.get('name') or node_id)
            details = [record.get('job_title'), record.get('department_id')]
            node['subtitle'] = ' — '.join(str(value) for value in details if value)
        elif record.get('name'):
            node['label'] = str(record['name'])
        nodes.append(node)
        selected_ids.add(node_id)
        selected_records[node_id] = record

    if not nodes:
        raise DiagramSpecError('Sơ đồ cần ít nhất một node từ dữ liệu database.')

    employee_chart = bool(nodes) and all(sources.get(node['id']) == 'employees' for node in nodes)
    if employee_chart and diagram_type == 'org_chart':
        edges = []
        for node_id, record in selected_records.items():
            parent_id = record.get('parent_id_record_id')
            if parent_id not in (None, False, '') and str(parent_id) in selected_ids:
                edges.append({'source': str(parent_id), 'target': node_id, 'label': 'Quản lý trực tiếp'})
    elif diagram_type == 'employee_list':
        edges = []
    else:
        edges = []
        for raw_edge in normalized.get('edges') or []:
            if not isinstance(raw_edge, dict):
                continue
            source = str(raw_edge.get('source') or '').strip()
            target = str(raw_edge.get('target') or '').strip()
            if source not in selected_ids or target not in selected_ids:
                raise DiagramSpecError('Sơ đồ chứa liên kết đến bản ghi không có trong dữ liệu đã xác minh.')
            edges.append(dict(raw_edge, source=source, target=target))

    normalized['nodes'] = nodes
    normalized['edges'] = edges
    return normalized
