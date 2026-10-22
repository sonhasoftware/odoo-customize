# -*- coding: utf-8 -*-
import base64
import json
import logging
import re
import requests
import time
import werkzeug
import odoo
from odoo.http import request

from ..utils.security_utils import (
    normalize_model_name,
    extract_gemini_error,
    gemini_user_error_message,
)
from .rate_limiter import check_rate_limit, RATE_LIMIT_MAX_MESSAGES
from .prompt_builder import (
    build_system_instruction,
    build_ollama_system_instruction,
    sanitize_technical_terms,
    normalize_step_lists,
    bold_ui_action_terms,
)
from .sql_engine import execute_odoo_query, execute_mssql_query
from .query_rewriter import rewrite_search_query
from .document_routing import resolve_document_route
from .ollama_options import build_ollama_chat_options, build_ollama_chat_timeout
from .chat_attachment import prepare_chat_attachment, ChatAttachmentError
from .rag_engine import retrieve_context
from .diagram_service import render_svg, DiagramSpecError
from .hybrid_pipeline import (
    QUERY_TOOL_NAMES,
    build_gemini_handoff_prompt,
    collect_query_context,
    query_tools_only,
    validate_and_normalize_diagram,
)

_logger = logging.getLogger(__name__)


class ChatService:
    """Core service for orchestrating AI Chatbot interactions (both synchronous and SSE streaming)."""

    def __init__(self, env):
        self.env = env

    @staticmethod
    def _convert_to_ollama_tools(tools_list):
        """Convert Gemini-formatted tools to standard OpenAI/Ollama tool declarations."""
        if not tools_list:
            return None

        def _lower_types(obj):
            if isinstance(obj, dict):
                new_obj = {}
                for k, v in obj.items():
                    if k == 'type' and isinstance(v, str):
                        new_obj[k] = v.lower()
                    else:
                        new_obj[k] = _lower_types(v)
                return new_obj
            elif isinstance(obj, list):
                return [_lower_types(x) for x in obj]
            return obj

        ollama_tools = []
        for t in tools_list:
            ollama_tools.append({
                'type': 'function',
                'function': {
                    'name': t['name'],
                    'description': t.get('description', ''),
                    'parameters': _lower_types(t.get('parameters', {}))
                }
            })
        return ollama_tools

    @staticmethod
    def _build_ollama_messages(system_instruction, contents):
        """Build messages payload for Ollama /api/chat from Gemini system instruction & contents."""
        messages = [{'role': 'system', 'content': system_instruction}]
        for item in contents:
            role = 'user' if item.get('role') == 'user' else 'assistant'
            parts = item.get('parts', [])
            text_parts = [p.get('text', '') for p in parts if 'text' in p]
            text_content = "\n".join(text_parts).strip()
            if text_content:
                messages.append({'role': role, 'content': text_content})
        return messages

    @staticmethod
    def _convert_to_openai_tools(tools_list):
        """Convert the provider-neutral declarations to OpenAI function tools."""
        return ChatService._convert_to_ollama_tools(tools_list)

    @staticmethod
    def _build_openai_messages(system_instruction, contents):
        messages = [{'role': 'system', 'content': system_instruction}]
        for item in contents:
            role = 'user' if item.get('role') == 'user' else 'assistant'
            text_content = "\n".join(
                part.get('text', '') for part in item.get('parts', []) if part.get('text')
            ).strip()
            if text_content:
                messages.append({'role': role, 'content': text_content})
        return messages

    @staticmethod
    def _detach_generated_diagram(result):
        """Remove private attachment bytes before returning tool output to an LLM."""
        if not isinstance(result, dict):
            return result, None
        public_result = dict(result)
        attachment = public_result.pop('_diagram_attachment', None)
        return public_result, attachment

    def _run_hybrid_ollama_stage(self, pipeline_data, env, topic):
        """Use Ollama to query/summarize, then return a verified hand-off packet."""
        data_tools = query_tools_only(pipeline_data.get('tools_list', []))
        ollama_tools = self._convert_to_ollama_tools(data_tools)
        system_instruction = (
            "Bạn là tầng tiền xử lý dữ liệu nội bộ trước Gemini. "
            "Nếu có công cụ truy vấn và câu hỏi cần dữ liệu thực tế, bắt buộc gọi công cụ trước. "
            "Không được gọi công cụ tạo sơ đồ. Không tự thêm dữ liệu. "
            "Sau khi nhận kết quả, hãy tóm tắt ngắn gọn và giữ nguyên id, họ tên, chức danh, "
            "phòng ban, parent_id và trạng thái truncated. "
            "Kết quả cuối nên là JSON với các khóa summary, selected_record_ids và truncated."
        )
        messages = self._build_ollama_messages(system_instruction, pipeline_data['contents'])
        events = []
        summary = ''
        call_count = 0
        retry_without_query = False

        for round_index in range(4):
            payload = {
                'model': pipeline_data['ollama_chat_model'],
                'messages': messages,
                'stream': False,
                'options': build_ollama_chat_options(pipeline_data.get('ollama_num_ctx')),
            }
            # Reserve the final round for synthesis so Ollama cannot loop tools forever.
            if ollama_tools and round_index < 3:
                payload['tools'] = ollama_tools
            response = requests.post(
                f"{pipeline_data['ollama_url']}/api/chat",
                json=payload,
                timeout=build_ollama_chat_timeout(pipeline_data.get('ollama_read_timeout')),
            )
            call_count += 1
            response.raise_for_status()
            message = response.json().get('message') or {}
            tool_calls = message.get('tool_calls') or []
            if tool_calls:
                messages.append(message)
                for tool_call in tool_calls:
                    function = tool_call.get('function') or {}
                    name = function.get('name')
                    args = function.get('arguments') or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (TypeError, ValueError):
                            args = {}
                    if name not in QUERY_TOOL_NAMES:
                        result = {'error': 'Tầng Ollama chỉ được phép truy vấn dữ liệu.'}
                    else:
                        result = self._execute_tool(name, args, env, topic)
                        events.append({'name': name, 'args': args, 'result': result})
                    messages.append({
                        'role': 'tool',
                        'content': json.dumps(result, ensure_ascii=False, default=str),
                    })
                continue

            summary = str(message.get('content') or '').strip()
            if data_tools and not events and not retry_without_query and round_index < 2:
                retry_without_query = True
                messages.append(message)
                messages.append({
                    'role': 'user',
                    'content': (
                        'Bạn chưa truy vấn database. Hãy gọi công cụ dữ liệu phù hợp trước khi tóm tắt. '
                        'Nếu phạm vi toàn công ty quá lớn, vẫn truy vấn và giữ nguyên cờ truncated.'
                    ),
                })
                summary = ''
                continue
            break

        query_context = collect_query_context(events)
        # Ollama may fetch an employee but omit the manager record itself.
        # Hydrate one direct-manager level deterministically so Gemini can only
        # draw a manager node that was read from the database.
        employee_records = [
            record
            for batch in query_context.get('batches', [])
            if batch.get('source') == 'employees'
            for record in (batch.get('records') or [])
            if isinstance(record, dict)
        ]
        existing_ids = {
            int(record['id']) for record in employee_records
            if str(record.get('id') or '').isdigit()
        }
        manager_ids = {
            int(record['parent_id_record_id']) for record in employee_records
            if str(record.get('parent_id_record_id') or '').isdigit()
            and int(record['parent_id_record_id']) not in existing_ids
        }
        if manager_ids:
            manager_result = execute_odoo_query(
                model='employees',
                domain=[['id', 'in', sorted(manager_ids)]],
                fields=['id', 'name', 'job_title', 'department_id', 'parent_id'],
                env=env,
            )
            events.append({
                'name': 'query_odoo_data',
                'args': {'model': 'employees', 'domain': [['id', 'in', sorted(manager_ids)]]},
                'result': manager_result,
            })
            query_context = collect_query_context(events)
        if not summary:
            summary = json.dumps({
                'summary': 'Ollama đã hoàn tất bước tiền xử lý.',
                'selected_record_ids': [],
                'truncated': query_context.get('truncated', False),
            }, ensure_ascii=False)
        return summary, query_context, call_count

    @staticmethod
    def _hybrid_gemini_tools(tools_list, query_context):
        """Gemini may render verified data, but may not run a second query."""
        if (query_context or {}).get('truncated'):
            return []
        if not (query_context or {}).get('batches'):
            return []
        return [tool for tool in (tools_list or []) if tool.get('name') == 'render_data_diagram']

    def _execute_hybrid_gemini_tool(self, func_name, func_args, env, topic, query_context):
        if func_name != 'render_data_diagram':
            return {'error': 'Gemini chỉ được phép dựng sơ đồ từ dữ liệu đã xác minh.'}
        try:
            verified_args = validate_and_normalize_diagram(func_args, query_context)
        except DiagramSpecError as error:
            return {'error': str(error)}
        return self._execute_tool(func_name, verified_args, env, topic)

    def _run_openai_chat(self, pipeline_data, env, topic):
        """Run a bounded OpenAI function-calling loop and return text + diagram."""
        api_key = pipeline_data.get('openai_api_key')
        base_url = (pipeline_data.get('openai_base_url') or 'https://api.openai.com/v1').rstrip('/')
        model = pipeline_data.get('openai_model') or 'gpt-4o-mini'
        messages = self._build_openai_messages(
            pipeline_data['system_instruction'], pipeline_data['contents']
        )
        tools = self._convert_to_openai_tools(pipeline_data.get('tools_list', []))
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }
        generated_diagram = None
        tool_calls_count = 0

        for _round in range(5):
            payload = {
                'model': model,
                'messages': messages,
                'temperature': 0,
                'max_tokens': 8192,
            }
            if tools:
                payload['tools'] = tools
                payload['tool_choice'] = 'auto'
            response = requests.post(
                f'{base_url}/chat/completions', headers=headers, json=payload, timeout=120
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get('choices') or []
            if not choices:
                raise ValueError('OpenAI API không trả về lựa chọn câu trả lời.')
            assistant = choices[0].get('message') or {}
            tool_calls = assistant.get('tool_calls') or []
            if not tool_calls:
                return assistant.get('content') or '', generated_diagram, tool_calls_count

            tool_calls_count += len(tool_calls)
            messages.append({
                'role': 'assistant',
                'content': assistant.get('content') or '',
                'tool_calls': tool_calls,
            })
            for call in tool_calls:
                function = call.get('function') or {}
                args = function.get('arguments') or '{}'
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (TypeError, ValueError):
                        args = {}
                result = self._execute_tool(function.get('name'), args, env, topic)
                public_result, attachment = self._detach_generated_diagram(result)
                if attachment:
                    generated_diagram = attachment
                messages.append({
                    'role': 'tool',
                    'tool_call_id': call.get('id'),
                    'content': json.dumps(public_result, ensure_ascii=False, default=str),
                })

        raise ValueError('Mô hình gọi công cụ quá nhiều vòng mà chưa tạo được câu trả lời.')

    def _execute_tool(self, func_name, func_args, env, topic):
        """Execute a read-only query or render a validated data diagram."""
        _logger.info(
            "[CHAT_TOOL_EXECUTION] Tool invoked: '%s' | Args: %s",
            func_name,
            json.dumps(func_args, ensure_ascii=False) if isinstance(func_args, dict) else str(func_args)
        )
        if func_name == 'query_odoo_data':
            res = execute_odoo_query(
                model=func_args.get('model'),
                domain=func_args.get('domain'),
                fields=func_args.get('fields'),
                env=env
            )
            _logger.info(
                "[CHAT_TOOL_EXECUTION] Result of 'query_odoo_data': %s",
                f"{len(res)} item(s)" if isinstance(res, list) else ("dict/error: " + str(res)[:120])
            )
            # Make the cardinality explicit for document catalog queries.  LLMs
            # occasionally summarize a returned list and omit the last item even
            # though the ORM query returned it.  The count plus the exact rows
            # instruct the model to enumerate every published document.
            if func_args.get('model') in ('decision_documents', 'decision.document') and isinstance(res, list):
                return {
                    'record_count': len(res),
                    'records': res,
                    'instruction': (
                        'Kết quả đã được lấy trực tiếp từ database. BẮT BUỘC liệt kê đủ '
                        'record_count bản ghi trong trường records, không được bỏ sót hoặc gộp bản ghi.'
                    ),
                }
            return res
        elif func_name == 'query_sql_server_data':
            res = execute_mssql_query(
                sql_query=func_args.get('sql_query', ''),
                topic=topic,
                env=env
            )
            _logger.info(
                "[CHAT_TOOL_EXECUTION] Result of 'query_sql_server_data': %s",
                f"{len(res)} item(s)" if isinstance(res, list) else ("dict/error: " + str(res)[:120])
            )
            return res
        elif func_name == 'render_data_diagram':
            try:
                rendered = render_svg(func_args)
                return {
                    'success': True,
                    'title': rendered['title'],
                    'diagram_type': rendered['diagram_type'],
                    'node_count': rendered['node_count'],
                    'edge_count': rendered['edge_count'],
                    'message': 'Sơ đồ đã được tạo và sẽ hiển thị trong câu trả lời.',
                    '_diagram_attachment': {
                        'attachment_name': rendered['filename'],
                        'attachment_mimetype': 'image/svg+xml',
                        'attachment_data': base64.b64encode(rendered['svg_bytes']),
                    },
                }
            except DiagramSpecError as error:
                return {'error': str(error)}
        return {'error': f"Unknown function '{func_name}'"}

    @staticmethod
    def _append_missing_document_rows(reply_text, document_results):
        """Ensure a model cannot silently omit rows returned by the document query."""
        if not document_results:
            return reply_text
        missing = []
        for result in document_results:
            rows = result.get('records', []) if isinstance(result, dict) else []
            for row in rows:
                identity = ' '.join(str(row.get(k) or '') for k in ('reference', 'name', 'id'))
                if identity and not all(str(value) in (reply_text or '') for value in (row.get('reference') or row.get('name') or '',)):
                    missing.append(row)
        if not missing:
            return reply_text
        lines = ['\n\n**Danh sách đầy đủ từ database:**']
        for row in missing:
            label = row.get('reference') or row.get('name') or row.get('id')
            name = row.get('name') or ''
            url = row.get('file_url') or row.get('record_url') or ''
            lines.append(f"- **{label}** — {name}" + (f" — [Mở tài liệu]({url})" if url else ''))
        return (reply_text or '').rstrip() + '\n' + '\n'.join(lines)

    def prepare_chat_pipeline(self, conversation, message):
        """Common pre-processing pipeline for both ask and ask_stream:
        1. Read config params (API key, model, provider)
        2. Rewrite query & extract filters
        3. RAG context retrieval
        4. Build system instruction
        5. Build chat history payload
        6. Build function declaration tools
        """
        env = self.env
        topic = conversation.topic_id
        attachment_message = env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation.id),
            ('role', '=', 'user'),
            ('attachment_text', '!=', False),
        ], order='id desc', limit=1)

        params = env['ir.config_parameter'].sudo()
        llm_provider = params.get_param('topic_chatbot.llm_provider', default='gemini') or 'gemini'
        ollama_url = (params.get_param('topic_chatbot.ollama_url') or 'http://localhost:11434').rstrip('/')
        ollama_chat_model = params.get_param('topic_chatbot.ollama_chat_model', default='qwen2.5:14b') or 'qwen2.5:14b'

        api_key = params.get_param('topic_chatbot.gemini_api_key')
        raw_model = params.get_param('topic_chatbot.gemini_model', default='gemini-3.6-flash')
        model = normalize_model_name(raw_model)
        openai_api_key = params.get_param('topic_chatbot.openai_api_key')
        openai_model = params.get_param('topic_chatbot.openai_model', default='gpt-4o-mini') or 'gpt-4o-mini'
        openai_base_url = (
            params.get_param('topic_chatbot.openai_base_url', default='https://api.openai.com/v1')
            or 'https://api.openai.com/v1'
        ).rstrip('/')

        if llm_provider in ('gemini', 'hybrid') and not api_key:
            return None, {'error': 'Chưa cấu hình Gemini API Key. Vui lòng vào menu Cấu hình để nhập API Key.'}
        if llm_provider == 'openai' and not openai_api_key:
            return None, {'error': 'Chưa cấu hình OpenAI API Key. Vui lòng vào menu Cấu hình để nhập API Key.'}

        if attachment_message:
            search_query, filters, is_valid = message, {}, True
            route_type, structured_query = 'SEMANTIC_RAG', None
            route_reason = 'Ưu tiên nội dung tệp đính kèm trong hội thoại'
        else:
            # Hybrid guarantees that Ollama is the first model processing the
            # request. Use the deterministic rewriter fallback before that,
            # instead of making an early Gemini request.
            rewrite_api_key = None if llm_provider == 'hybrid' else api_key
            rewriter_res = rewrite_search_query(env, message, conversation.id, rewrite_api_key, model)
            route_reason = "Không xác định"
            if len(rewriter_res) >= 6:
                search_query, filters, is_valid, route_type, structured_query, route_reason = rewriter_res[:6]
            elif len(rewriter_res) == 5:
                search_query, filters, is_valid, route_type, structured_query = rewriter_res
            else:
                search_query, filters, is_valid, route_type = rewriter_res[:4]
                structured_query = message if route_type == 'STRUCTURED_DATA' else None

        resolved_route = resolve_document_route(route_type, topic, original_query=message)
        if resolved_route != route_type:
            route_reason = (
                f"{route_reason}; chuyển {route_type} sang {resolved_route}: "
                "câu hỏi cần tra cứu nội dung tài liệu"
            )
            route_type = resolved_route
            structured_query = None

        chunks = [] if attachment_message else retrieve_context(
            env,
            topic.id,
            search_query,
            filters=filters,
            original_query=message,
            is_valid=is_valid,
            route_type=route_type,
            structured_query=structured_query
        )

        structured_engine_called = (route_type == 'STRUCTURED_DATA')
        if structured_engine_called and chunks and chunks[0].get('structured_data'):
            s_data = chunks[0]['structured_data']
            structured_result_count = s_data.get('result_count', 0)
            structured_filters_str = json.dumps(s_data.get('filters', []), ensure_ascii=False)
        else:
            structured_result_count = 0
            structured_filters_str = json.dumps(filters or {}, ensure_ascii=False)

        _logger.info(
            "\n[QUERY_TRACE]\nraw_query = %s\n\n"
            "[QUERY_TRACE]\nroute_type = %s\n\n"
            "[QUERY_TRACE]\nroute_reason = %s\n\n"
            "[QUERY_TRACE]\nstructured_query = %s\n\n"
            "[QUERY_TRACE]\nstructured_engine_called = %s\n\n"
            "[QUERY_TRACE]\nstructured_filters = %s\n\n"
            "[QUERY_TRACE]\nstructured_result_count = %s",
            message,
            route_type,
            route_reason,
            json.dumps(structured_query, ensure_ascii=False) if isinstance(structured_query, dict) else (structured_query or "None"),
            structured_engine_called,
            structured_filters_str,
            structured_result_count
        )

        context_str = "\n\n".join([
            (
                chunk['content'] if chunk.get('chunk_type') == 'structured_result' else
                f"--- Topic: {chunk.get('topic_name', topic.name or '')} | Nguồn: {chunk['document_name']}, đoạn {chunk['sequence']} ---\n{chunk['content']}"
            )
            for chunk in chunks
        ])
        if attachment_message:
            context_str = (
                f"--- Tệp người dùng đính kèm: {attachment_message.attachment_name} ---\n"
                f"{attachment_message.attachment_text}"
            )

        _logger.info(
            "[FINAL_CONTEXT_USED]\n"
            "  - query_text: '%s'\n"
            "  - final_context_used:\n%s",
            message,
            context_str if context_str else "(No context chunks retrieved)"
        )

        # Log full RAG payload for observability & debugging
        try:
            from .rag_engine import log_rag_payload
            log_rag_payload(
                env=env,
                topic_id=topic.id,
                user_query=message,
                route_type=route_type,
                route_reason=route_reason,
                chunks=chunks,
                prompt_context=context_str,
                conversation_id=conversation.id,
                extra_data={
                    'search_query': search_query,
                    'filters': filters,
                    'structured_query': structured_query,
                    'is_valid': is_valid,
                    'llm_provider': llm_provider,
                }
            )
        except Exception as e_log:
            _logger.warning("Could not log RAG payload: %s", str(e_log))

        has_duyet_gia = "duyệt giá" in context_str.lower()
        has_tao_duyet_gia = "tạo duyệt giá" in context_str.lower()
        selected_doc_names = list(set(c.get('document_name') for c in chunks if c.get('document_name')))
        selected_parent_ids = [c.get('id') for c in chunks]

        _logger.info(
            "[RAG_DEBUG][CONTEXT]\n"
            "  - context_chars: %d\n"
            "  - context_block_count: %d\n"
            "  - document_count: %d\n"
            "  - has_keyword_duyet_gia: %s\n"
            "  - has_keyword_tao_duyet_gia: %s\n"
            "  - selected_document_names: %s\n"
            "  - selected_parent_ids: %s",
            len(context_str), len(chunks), len(selected_doc_names),
            has_duyet_gia, has_tao_duyet_gia,
            selected_doc_names, selected_parent_ids
        )

        available_topics = env['topic_chatbot.topic'].search([('id', '!=', topic.id)])
        other_topic_names = [t.name for t in available_topics if t.name]
        has_documents = bool(topic.document_ids) or bool(attachment_message)
        document_names = [d.name for d in topic.document_ids if d.name]
        if attachment_message:
            document_names.insert(0, attachment_message.attachment_name)

        is_mssql_active = not attachment_message and bool(
            topic.is_mssql_query or
            (topic.mssql_allowed_tables and topic.mssql_allowed_tables.strip()) or
            ('sql' in (topic.name or '').lower())
        )

        if llm_provider == 'ollama':
            system_instruction = build_ollama_system_instruction(
                context_str,
                topic_name=topic.name or '',
                topic_description=topic.description or '',
                other_topic_names=other_topic_names,
                document_names=document_names,
                is_db_query=topic.is_db_query and not attachment_message,
                is_mssql_query=is_mssql_active,
                mssql_tables=(topic.mssql_allowed_tables or "") + (f"\n\nCẤU TRÚC BẢNG:\n{topic.mssql_schema_info}" if topic.mssql_schema_info else ""),
                has_documents=has_documents
            )
        else:
            system_instruction = build_system_instruction(
                context_str,
                topic_name=topic.name or '',
                topic_description=topic.description or '',
                other_topic_names=other_topic_names,
                document_names=document_names,
                is_db_query=topic.is_db_query and not attachment_message,
                is_mssql_query=is_mssql_active,
                mssql_tables=(topic.mssql_allowed_tables or "") + (f"\n\nCẤU TRÚC BẢNG:\n{topic.mssql_schema_info}" if topic.mssql_schema_info else ""),
                has_documents=has_documents
            )

        # Multi-turn chat history windowing
        if not is_valid:
            contents = [{
                'role': 'user',
                'parts': [{'text': message}]
            }]
        else:
            db_messages = env['topic_chatbot.message'].search([
                ('conversation_id', '=', conversation.id)
            ], order='create_date desc')

            contents = []
            total_chars = 0
            context_chars = len(context_str) if context_str else 0
            MAX_CHARS = max(8000, 30000 - context_chars)

            for i, m in enumerate(db_messages):
                cleaned_content = re.sub(r' {2,}', ' ', m.content or '').strip()
                if not cleaned_content:
                    continue

                if total_chars + len(cleaned_content) > MAX_CHARS and len(contents) > 0:
                    break

                total_chars += len(cleaned_content)
                contents.insert(0, {
                    'role': 'user' if m.role == 'user' else 'model',
                    'parts': [{'text': cleaned_content}]
                })

        # Function Calling Tools definition
        tools_list = []
        if topic.is_db_query and not attachment_message:
            tools_list.append({
                'name': 'query_odoo_data',
                'description': (
                    'Truy vấn đọc dữ liệu (Read-only) an toàn từ database Odoo '
                    'để tìm thông tin liên quan đến các dữ liệu nghiệp vụ: Nhân viên, '
                    'Phòng ban, Kết quả KPI tháng, Đánh giá KPI của lãnh đạo, KPI năm.\n'
                    'CHỈ sử dụng công cụ này khi người dùng hỏi các câu hỏi thực tế về dữ liệu '
                    'hệ thống Odoo (như KPI, danh sách nhân viên, cấp quản lý, các luồng duyệt '
                    'và kho quyết định/tài liệu đã công bố). Khi chủ đề là "Tra cứu quyết định", '
                    'BẮT BUỘC dùng nguồn "decision_documents" và trả đường dẫn file dưới dạng '
                    'liên kết Markdown có thể bấm.\n'
                    '(LƯU Ý BẢO MẬT: Tuyệt đối không nhắc đến tên công cụ này hoặc chữ API trong câu trả lời người dùng).'
                ),
                'parameters': {
                    'type': 'OBJECT',
                    'properties': {
                        'model': {
                            'type': 'STRING',
                            'description': (
                                'Mã định danh nguồn dữ liệu nội bộ cần truy vấn. '
                                'Chỉ chấp nhận đúng một trong các giá trị sau: '
                                '"employees", "departments", "kpi_month_results", '
                                '"kpi_month_report", "kpi_year_results", "hr_approval_requests", '
                                '"car_approval_config", "document_approval_steps", "decision_documents". '
                                'Dùng "decision_documents" để tìm theo tên, số/ký hiệu, từ khóa, '
                                'tóm tắt, danh mục, phòng ban, nhân viên, người ký hoặc ngày ban hành. '
                                'Nếu người dùng dùng các từ "tất cả", "toàn bộ", "danh sách tất cả" hoặc '
                                '"đã công bố" mà không nêu bộ lọc cụ thể, bắt buộc truyền domain là [] '
                                '(hệ thống tự lọc state=published) và phải liệt kê mọi bản ghi trả về.'
                            )
                        },
                        'domain': {
                            'type': 'STRING',
                            'description': 'Mảng các điều kiện lọc dạng Odoo Domain (chuỗi JSON).'
                        },
                        'fields': {
                            'type': 'ARRAY',
                            'items': {'type': 'STRING'},
                            'description': (
                                'Mảng tên trường cần lấy. Khi vẽ sơ đồ tổ chức hoặc hỏi cấp quản lý nhân viên, '
                                'hãy lấy tối thiểu id, name, job_title, department_id và parent_id. '
                                'Khi tìm quyết định, hãy lấy name, reference, issue_date, category_id, '
                                'department_id, employee_id, signer, summary, file_url và state.'
                            )
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
                    'để lấy danh sách các cột trước, sau đó mới gọi lại công cụ này với điều kiện WHERE chính xác.\n'
                    '(LƯU Ý BẢO MẬT: Tuyệt đối không nhắc đến tên công cụ này hoặc chữ API trong câu trả lời người dùng).'
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

        if tools_list:
            tools_list.append({
                'name': 'render_data_diagram',
                'description': (
                    'Tạo ảnh SVG từ dữ liệu thực tế đã truy vấn. Chỉ gọi khi người dùng yêu cầu sơ đồ, '
                    'flowchart, luồng duyệt, cây quản lý hoặc sơ đồ tổ chức. Bắt buộc truy vấn dữ liệu trước, '
                    'sau đó chuyển đúng dữ liệu đã nhận thành nodes và edges; không tự thêm người hoặc bước. '
                    'Với sơ đồ tổ chức, cạnh đi từ quản lý đến nhân viên. Với luồng duyệt, cạnh đi theo thứ tự duyệt.'
                ),
                'parameters': {
                    'type': 'OBJECT',
                    'properties': {
                        'title': {'type': 'STRING', 'description': 'Tiêu đề tiếng Việt của sơ đồ.'},
                        'diagram_type': {
                            'type': 'STRING',
                            'enum': ['flowchart', 'org_chart', 'employee_list'],
                            'description': 'Loại sơ đồ cần vẽ.'
                        },
                        'nodes': {
                            'type': 'ARRAY',
                            'description': 'Các đối tượng có thật trong kết quả truy vấn.',
                            'items': {
                                'type': 'OBJECT',
                                'properties': {
                                    'id': {'type': 'STRING'},
                                    'label': {'type': 'STRING'},
                                    'subtitle': {'type': 'STRING'},
                                    'status': {
                                        'type': 'STRING',
                                        'enum': ['normal', 'start', 'end', 'approved', 'pending', 'rejected']
                                    }
                                },
                                'required': ['id', 'label']
                            }
                        },
                        'edges': {
                            'type': 'ARRAY',
                            'items': {
                                'type': 'OBJECT',
                                'properties': {
                                    'source': {'type': 'STRING'},
                                    'target': {'type': 'STRING'},
                                    'label': {'type': 'STRING'}
                                },
                                'required': ['source', 'target']
                            }
                        }
                    },
                    'required': ['title', 'diagram_type', 'nodes', 'edges']
                }
            })

        tools = [{'functionDeclarations': tools_list}] if tools_list else None

        pipeline_data = {
            'ollama_num_ctx': params.get_param('topic_chatbot.ollama_num_ctx', default='16384'),
            'ollama_read_timeout': params.get_param('topic_chatbot.ollama_read_timeout', default='900'),
            'llm_provider': llm_provider,
            'ollama_url': ollama_url,
            'ollama_chat_model': ollama_chat_model,
            'api_key': api_key,
            'model': model,
            'openai_api_key': openai_api_key,
            'openai_model': openai_model,
            'openai_base_url': openai_base_url,
            'context_str': context_str,
            'system_instruction': system_instruction,
            'contents': contents,
            'tools': tools,
            'tools_list': tools_list,
            'topic': topic,
            'search_query': search_query,
        }
        return pipeline_data, None

    def handle_ask(self, conversation_id, message, attachment=None):
        """Synchronous chat processing (/topic_chatbot/ask)."""
        env = self.env
        message = (message or '').strip()
        if not message and attachment:
            message = 'Hãy phân tích tệp đính kèm này.'
        if not message:
            return {'error': 'Vui lòng nhập câu hỏi hoặc đính kèm tệp.'}
        try:
            conversation_id_int = int(conversation_id)
        except (ValueError, TypeError):
            return {'error': 'Conversation not found or access denied.'}

        conversation = env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', env.uid)
        ], limit=1)
        if not conversation:
            return {'error': 'Conversation not found or access denied.'}

        if check_rate_limit(env, env.uid):
            return {'error': f'Bạn đã gửi quá {RATE_LIMIT_MAX_MESSAGES} câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại.'}

        if conversation.is_processing:
            return {'error': 'Vui lòng chờ câu trả lời trước hoàn tất trước khi gửi câu hỏi mới.'}
        conversation.sudo().write({'is_processing': True})

        topic = env['topic_chatbot.topic'].sudo().browse(conversation.topic_id.id)
        if not topic.exists():
            conversation.sudo().write({'is_processing': False})
            return {'error': 'Truy cập vào chủ đề này bị từ chối hoặc không khả dụng.'}

        bot_reply_saved = False
        user_message = None
        try:
            attachment_values = prepare_chat_attachment(env, attachment, message) if attachment else {}
            # Save user message
            user_message = env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'user',
                'content': message,
                **attachment_values,
            })

            pipeline_data, err = self.prepare_chat_pipeline(conversation, message)
            if err:
                return err

            llm_provider = pipeline_data.get('llm_provider', 'gemini')
            api_key = pipeline_data['api_key']
            model = pipeline_data['model']
            system_instruction = pipeline_data['system_instruction']
            contents = pipeline_data['contents']
            tools = pipeline_data['tools']
            tools_list = pipeline_data.get('tools_list', [])

            request_start_time = time.time()
            ttft = None
            prompt_eval_duration = 0.0
            probe_calls = 0
            generation_calls = 0
            tool_calls_count = 0

            reply_text = ""
            reply_segments = []
            generated_diagram = None
            document_query_results = []
            hybrid_query_context = None

            if llm_provider == 'hybrid':
                ollama_summary, hybrid_query_context, hybrid_calls = self._run_hybrid_ollama_stage(
                    pipeline_data, env, topic
                )
                generation_calls += hybrid_calls
                handoff_prompt = build_gemini_handoff_prompt(ollama_summary, hybrid_query_context)
                contents = list(contents) + [{
                    'role': 'user',
                    'parts': [{'text': handoff_prompt}],
                }]
                hybrid_tools = self._hybrid_gemini_tools(tools_list, hybrid_query_context)
                tools = [{'functionDeclarations': hybrid_tools}] if hybrid_tools else None

            if llm_provider == 'ollama':
                ollama_url = pipeline_data['ollama_url']
                ollama_model = pipeline_data['ollama_chat_model']
                ollama_tools = self._convert_to_ollama_tools(tools_list)
                ollama_messages = self._build_ollama_messages(system_instruction, contents)

                api_call_count = 0
                while api_call_count < 3:
                    api_call_count += 1
                    generation_calls += 1
                    ollama_payload = {
                        'model': ollama_model,
                        'messages': ollama_messages,
                        'stream': False,
                        'options': build_ollama_chat_options(pipeline_data.get('ollama_num_ctx'))
                    }
                    if ollama_tools:
                        ollama_payload['tools'] = ollama_tools

                    response = requests.post(f"{ollama_url}/api/chat", json=ollama_payload, timeout=build_ollama_chat_timeout(pipeline_data.get('ollama_read_timeout')))
                    response.raise_for_status()
                    res_data = response.json()
                    p_eval = res_data.get('prompt_eval_duration', 0) / 1e9
                    if p_eval > 0:
                        prompt_eval_duration += p_eval
                    msg = res_data.get('message', {})
                    tool_calls = msg.get('tool_calls', [])

                    if tool_calls:
                        tool_calls_count += len(tool_calls)
                        _logger.info(
                            "ask (Ollama): Model emitted %d tool call(s): %s",
                            len(tool_calls),
                            [tc.get('function', {}).get('name') for tc in tool_calls]
                        )
                        ollama_messages.append(msg)
                        for tc in tool_calls:
                            f_info = tc.get('function', {})
                            f_name = f_info.get('name')
                            f_args = f_info.get('arguments', {})
                            if isinstance(f_args, str):
                                try:
                                    f_args = json.loads(f_args)
                                except Exception:
                                    f_args = {}
                            t_res = self._execute_tool(f_name, f_args, env, topic)
                            if f_name == 'query_odoo_data' and f_args.get('model') in ('decision_documents', 'decision.document') and isinstance(t_res, dict) and t_res.get('records'):
                                document_query_results.append(t_res)
                            t_res, attachment = self._detach_generated_diagram(t_res)
                            if attachment:
                                generated_diagram = attachment
                            ollama_messages.append({
                                'role': 'tool',
                                'content': json.dumps(t_res, ensure_ascii=False)
                            })
                        continue
                    else:
                        if ttft is None:
                            ttft = time.time() - request_start_time
                        reply_text = msg.get('content', '')
                        break
            elif llm_provider == 'openai':
                reply_text, generated_diagram, openai_tool_calls = self._run_openai_chat(
                    pipeline_data, env, topic
                )
                tool_calls_count += openai_tool_calls
                generation_calls += 1
                ttft = time.time() - request_start_time
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                headers = {'Content-Type': 'application/json'}
                payload = {
                    'contents': contents,
                    'systemInstruction': {'parts': [{'text': system_instruction}]},
                    'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.0}
                }
                if tools:
                    payload['tools'] = tools
                    payload['toolConfig'] = {'functionCallingConfig': {'mode': 'AUTO'}}

                api_call_count = 0
                continuation_count = 0
                max_continuations = 4

                while api_call_count < 3:
                    generation_calls += 1
                    response = requests.post(url, headers=headers, json=payload, timeout=90)
                    if ttft is None:
                        ttft = time.time() - request_start_time
                    response.raise_for_status()
                    res_data = response.json()

                    function_calls = []
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
                        tool_calls_count += len(function_calls)
                        tool_parts = []
                        for func_call in function_calls:
                            func_name = func_call.get('name')
                            func_args = func_call.get('args', {})

                            if llm_provider == 'hybrid':
                                result = self._execute_hybrid_gemini_tool(
                                    func_name, func_args, env, topic, hybrid_query_context
                                )
                            else:
                                result = self._execute_tool(func_name, func_args, env, topic)
                            if func_name == 'query_odoo_data' and func_args.get('model') in ('decision_documents', 'decision.document') and isinstance(result, dict) and result.get('records'):
                                document_query_results.append(result)
                            result, attachment = self._detach_generated_diagram(result)
                            if attachment:
                                generated_diagram = attachment

                            function_response = {
                                'name': func_name,
                                'response': {'result': result}
                            }
                            if func_call.get('id'):
                                function_response['id'] = func_call.get('id')
                            tool_parts.append({'functionResponse': function_response})

                        contents.append({'role': 'model', 'parts': model_parts})
                        contents.append({'role': 'user', 'parts': tool_parts})
                        payload['contents'] = contents
                        api_call_count += 1
                    else:
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
                                current_reply_text = "\n".join(all_parts_text)
                                if current_reply_text:
                                    reply_segments.append(current_reply_text)
                                    reply_text = "\n".join(reply_segments)

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

            total_time = time.time() - request_start_time
            ttft_str = f"{ttft:.2f}s" if ttft is not None else "N/A"
            prompt_eval_str = f"{prompt_eval_duration:.2f}s" if prompt_eval_duration > 0 else "N/A"
            if llm_provider == 'ollama':
                active_model = ollama_model
            elif llm_provider == 'openai':
                active_model = pipeline_data.get('openai_model') or 'gpt-4o-mini'
            else:
                active_model = model or 'gemini-3.6-flash'

            _logger.info(
                "\n[CHAT_PERF_TRACE]\n"
                "provider = %s\n"
                "model = %s\n"
                "probe_calls = %d\n"
                "generation_calls = %d\n"
                "tool_calls = %d\n"
                "ttft = %s\n"
                "prompt_eval_duration = %s\n"
                "total_time = %.2fs",
                llm_provider,
                active_model,
                probe_calls,
                generation_calls,
                tool_calls_count,
                ttft_str,
                prompt_eval_str,
                total_time
            )

            # Sanitize & cleanup
            reply_text = self._append_missing_document_rows(reply_text, document_query_results)
            reply_text = sanitize_technical_terms(reply_text, topic=topic)
            reply_text = normalize_step_lists(reply_text)
            if reply_text:
                reply_text = re.sub(r'-{10,}', '----------', reply_text)
                reply_text = re.sub(r' {10,}', ' ', reply_text)

            message_values = {
                'conversation_id': conversation.id,
                'role': 'model',
                'content': reply_text
            }
            if generated_diagram:
                message_values.update(generated_diagram)
            bot_message = env['topic_chatbot.message'].create(message_values)
            bot_reply_saved = True

            if conversation.name in ('New Chat', 'Cuộc trò chuyện mới') and len(message) > 0:
                new_name = message[:40] + ('...' if len(message) > 40 else '')
                conversation.write({'name': new_name})

            env.flush_all()
            env.cr.commit()

            result = {
                'response': reply_text,
                'conversation_name': conversation.name
            }
            if generated_diagram:
                result.update({
                    'attachment_name': bot_message.attachment_name,
                    'attachment_mimetype': bot_message.attachment_mimetype,
                    'attachment_url': f'/topic_chatbot/message_attachment/{bot_message.id}',
                })
            return result

        except ChatAttachmentError as error:
            return {'error': str(error)}
        except requests.exceptions.Timeout:
            _logger.error("Gemini API request timed out after 90 seconds")
            reply_text = "⏳ Câu hỏi của bạn cần thời gian xử lý lâu hơn dự kiến. Vui lòng thử lại với câu hỏi ngắn gọn hoặc cụ thể hơn."
            return {'response': reply_text, 'conversation_name': conversation.name}
        except requests.exceptions.HTTPError as e:
            response = getattr(e, 'response', None)
            params = env['ir.config_parameter'].sudo()
            api_key = params.get_param('topic_chatbot.gemini_api_key')
            error_details = extract_gemini_error(response, api_key) if response else {}
            _logger.error(
                "Gemini API returned HTTP %s (%s): %s",
                error_details.get('status_code'),
                error_details.get('status'),
                (error_details.get('message') or error_details.get('raw') or '')[:300],
            )
            reply_text = gemini_user_error_message(
                status_code=error_details.get('status_code'),
                error_status=error_details.get('status'),
                error_message=error_details.get('message') or error_details.get('raw'),
            )
            return {'response': reply_text, 'conversation_name': conversation.name}
        except Exception as e:
            params = env['ir.config_parameter'].sudo()
            api_key = params.get_param('topic_chatbot.gemini_api_key')
            err_msg = str(e)
            if api_key:
                err_msg = err_msg.replace(api_key, "REDACTED")
            _logger.error("Error communicating with Gemini API: %s", err_msg)
            reply_text = "Đã xảy ra lỗi khi kết nối tới AI. Vui lòng thử lại sau."
            return {'response': reply_text, 'conversation_name': conversation.name}
        finally:
            if not bot_reply_saved and user_message:
                try:
                    user_message.unlink()
                except Exception as e_orph:
                    _logger.error("Failed to clean up orphan message: %s", str(e_orph))
            conversation.sudo().write({'is_processing': False})

    def handle_ask_stream(self, httprequest_data):
        """Streaming chat processing with SSE (/topic_chatbot/ask_stream)."""
        data = json.loads(httprequest_data)
        conversation_id = data.get('conversation_id')
        attachment = data.get('attachment')
        message = (data.get('message') or '').strip()
        if not message and attachment:
            message = 'Hãy phân tích tệp đính kèm này.'

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

        env = self.env
        conversation = env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', env.uid)
        ], limit=1)
        if not conversation:
            return werkzeug.Response(
                json.dumps({'error': 'Conversation not found or access denied.'}),
                status=404,
                mimetype='application/json'
            )

        if check_rate_limit(env, env.uid):
            return werkzeug.Response(
                json.dumps({'error': f'Bạn đã gửi quá {RATE_LIMIT_MAX_MESSAGES} câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại.'}),
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

        topic = env['topic_chatbot.topic'].search([('id', '=', conversation.topic_id.id)])
        if not topic:
            conversation.sudo().write({'is_processing': False})
            return werkzeug.Response(
                json.dumps({'error': 'Truy cập vào chủ đề này bị từ chối hoặc không khả dụng.'}),
                status=403,
                mimetype='application/json'
            )

        try:
            attachment_values = prepare_chat_attachment(env, attachment, message) if attachment else {}
        except ChatAttachmentError as error:
            conversation.sudo().write({'is_processing': False})
            return werkzeug.Response(
                json.dumps({'error': str(error)}, ensure_ascii=False),
                status=400,
                mimetype='application/json'
            )

        env['topic_chatbot.message'].create({
            'conversation_id': conversation.id,
            'role': 'user',
            'content': message,
            **attachment_values,
        })
        env.flush_all()
        env.cr.commit()

        pipeline_data, err = self.prepare_chat_pipeline(conversation, message)
        if err:
            conversation.sudo().write({'is_processing': False})
            return werkzeug.Response(
                json.dumps(err),
                status=400,
                mimetype='application/json'
            )

        llm_provider = pipeline_data.get('llm_provider', 'gemini')
        ollama_url = pipeline_data.get('ollama_url')
        ollama_model = pipeline_data.get('ollama_chat_model')
        tools_list = pipeline_data.get('tools_list', [])

        api_key = pipeline_data['api_key']
        model = pipeline_data['model']
        system_instruction = pipeline_data['system_instruction']
        contents = pipeline_data['contents']
        tools = pipeline_data['tools']

        db_name = env.cr.dbname
        user_id = env.uid
        conversation_id = conversation.id
        topic_id = topic.id

        def generate():
            request_start_time = time.time()
            ttft = None
            prompt_eval_duration = 0.0
            probe_calls = 0
            generation_calls = 0
            tool_calls_count = 0

            final_reply = ""
            generated_diagram = None
            document_query_results = []
            continuation_count = 0
            max_continuations = 4
            clean_model = model or 'gemini-3.6-flash'

            models_to_try = [clean_model]
            if clean_model != 'gemini-3.5-flash-lite':
                models_to_try.append('gemini-3.5-flash-lite')

            req_headers = {'Content-Type': 'application/json'}
            local_contents = list(contents)
            active_gemini_tools = tools
            hybrid_query_context = None

            try:
                if llm_provider == 'hybrid':
                    yield f"data: {json.dumps({'type': 'status', 'content': 'Ollama đang truy vấn và tóm tắt dữ liệu nội bộ...'}, ensure_ascii=False)}\n\n"
                    try:
                        with odoo.registry(db_name).cursor() as cr:
                            gen_env = odoo.api.Environment(cr, user_id, {})
                            gen_topic = gen_env['topic_chatbot.topic'].browse(topic_id)
                            ollama_summary, hybrid_query_context, hybrid_calls = self._run_hybrid_ollama_stage(
                                pipeline_data, gen_env, gen_topic
                            )
                        generation_calls += hybrid_calls
                        tool_calls_count += len(hybrid_query_context.get('batches') or [])
                        local_contents.append({
                            'role': 'user',
                            'parts': [{
                                'text': build_gemini_handoff_prompt(ollama_summary, hybrid_query_context)
                            }],
                        })
                        hybrid_tools = self._hybrid_gemini_tools(tools_list, hybrid_query_context)
                        active_gemini_tools = (
                            [{'functionDeclarations': hybrid_tools}] if hybrid_tools else None
                        )
                        if hybrid_query_context.get('truncated'):
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Dữ liệu vượt giới hạn; Gemini sẽ yêu cầu thu hẹp phạm vi.'}, ensure_ascii=False)}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Dữ liệu đã được xác minh, đang chuyển sang Gemini...'}, ensure_ascii=False)}\n\n"
                    except Exception as hybrid_error:
                        safe_error = str(hybrid_error)
                        yield f"data: {json.dumps({'type': 'error', 'content': 'Không thể hoàn tất bước Ollama: ' + safe_error}, ensure_ascii=False)}\n\n"
                        return

                if llm_provider == 'ollama':
                    ollama_tools = self._convert_to_ollama_tools(tools_list)
                    ollama_messages = self._build_ollama_messages(system_instruction, contents)

                    tool_executed = False
                    # Probe tools if defined
                    if ollama_tools:
                        probe_calls += 1
                        try:
                            probe_payload = {
                                'model': ollama_model,
                                'messages': ollama_messages,
                                'stream': False,
                                'options': build_ollama_chat_options(pipeline_data.get('ollama_num_ctx')),
                                'tools': ollama_tools
                            }
                            probe_resp = requests.post(f"{ollama_url}/api/chat", json=probe_payload, timeout=build_ollama_chat_timeout(pipeline_data.get('ollama_read_timeout')))
                            if probe_resp.status_code == 200:
                                probe_data = probe_resp.json()
                                p_eval = probe_data.get('prompt_eval_duration', 0) / 1e9
                                if p_eval > 0:
                                    prompt_eval_duration += p_eval
                                msg = probe_data.get('message', {})
                                tool_calls = msg.get('tool_calls', [])
                                if tool_calls:
                                    tool_executed = True
                                    tool_calls_count += len(tool_calls)
                                    _logger.info(
                                        "ask_stream (Ollama): Model emitted %d tool call(s): %s",
                                        len(tool_calls),
                                        [tc.get('function', {}).get('name') for tc in tool_calls]
                                    )
                                    yield f"data: {json.dumps({'type': 'status', 'content': 'Đang truy vấn cơ sở dữ liệu...'}, ensure_ascii=False)}\n\n"
                                    ollama_messages.append(msg)
                                    with odoo.registry(db_name).cursor() as cr:
                                        gen_env = odoo.api.Environment(cr, user_id, {})
                                        gen_topic = gen_env['topic_chatbot.topic'].browse(topic_id)
                                        for tc in tool_calls:
                                            f_info = tc.get('function', {})
                                            f_name = f_info.get('name')
                                            f_args = f_info.get('arguments', {})
                                            if isinstance(f_args, str):
                                                try:
                                                    f_args = json.loads(f_args)
                                                except Exception:
                                                    f_args = {}
                                            t_res = self._execute_tool(f_name, f_args, gen_env, gen_topic)
                                            if f_name == 'query_odoo_data' and f_args.get('model') in ('decision_documents', 'decision.document') and isinstance(t_res, dict) and t_res.get('records'):
                                                document_query_results.append(t_res)
                                            t_res, attachment = self._detach_generated_diagram(t_res)
                                            if attachment:
                                                generated_diagram = attachment
                                            ollama_messages.append({
                                                'role': 'tool',
                                                'content': json.dumps(t_res, ensure_ascii=False)
                                            })
                                else:
                                    # Probe already generated the complete textual response!
                                    # ELIMINATE DOUBLE GENERATION: Yield text from probe directly!
                                    probe_content = msg.get('content', '')
                                    if probe_content:
                                        if ttft is None:
                                            ttft = time.time() - request_start_time
                                        final_reply = probe_content
                                        yield f"data: {json.dumps({'type': 'token', 'content': probe_content}, ensure_ascii=False)}\n\n"
                        except Exception as e_probe:
                            _logger.warning("Ollama tool probe failed: %s", str(e_probe))

                    # If no tools defined OR tool was executed (requiring final synthesis):
                    if not ollama_tools or tool_executed:
                        generation_calls += 1
                        stream_payload = {
                            'model': ollama_model,
                            'messages': ollama_messages,
                            'stream': True,
                            'options': build_ollama_chat_options(pipeline_data.get('ollama_num_ctx'))
                        }
                        try:
                            stream_resp = requests.post(
                                f"{ollama_url}/api/chat",
                                json=stream_payload,
                                stream=True,
                                timeout=build_ollama_chat_timeout(pipeline_data.get('ollama_read_timeout'))
                            )
                            if stream_resp.status_code == 200:
                                for line in stream_resp.iter_lines():
                                    if line:
                                        try:
                                            chunk = json.loads(line.decode('utf-8') if isinstance(line, bytes) else line)
                                            token = chunk.get('message', {}).get('content', '')
                                            if token:
                                                if ttft is None:
                                                    ttft = time.time() - request_start_time
                                                final_reply += token
                                                yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"
                                            if chunk.get('done'):
                                                p_eval = chunk.get('prompt_eval_duration', 0) / 1e9
                                                if p_eval > 0:
                                                    prompt_eval_duration += p_eval
                                        except Exception:
                                            continue
                            else:
                                err_str = f"Lỗi máy chủ Ollama: HTTP {stream_resp.status_code}"
                                yield f"data: {json.dumps({'type': 'error', 'content': err_str}, ensure_ascii=False)}\n\n"
                                return
                        except Exception as e_stream:
                            err_str = f"Lỗi kết nối máy chủ Ollama: {str(e_stream)}"
                            yield f"data: {json.dumps({'type': 'error', 'content': err_str}, ensure_ascii=False)}\n\n"
                            return
                elif llm_provider == 'openai':
                    yield f"data: {json.dumps({'type': 'status', 'content': 'Đang truy vấn và dựng sơ đồ dữ liệu...'}, ensure_ascii=False)}\n\n"
                    with odoo.registry(db_name).cursor() as cr:
                        gen_env = odoo.api.Environment(cr, user_id, {})
                        gen_topic = gen_env['topic_chatbot.topic'].browse(topic_id)
                        final_reply, generated_diagram, openai_tool_calls = self._run_openai_chat(
                            pipeline_data, gen_env, gen_topic
                        )
                    tool_calls_count += openai_tool_calls
                    generation_calls += 1
                    if final_reply:
                        ttft = time.time() - request_start_time
                        yield f"data: {json.dumps({'type': 'token', 'content': final_reply}, ensure_ascii=False)}\n\n"
                else:
                    while continuation_count <= max_continuations:
                        payload = {
                            'contents': local_contents,
                            'systemInstruction': {'parts': [{'text': system_instruction}]},
                            'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.0}
                        }
                        if active_gemini_tools:
                            payload['tools'] = active_gemini_tools
                            payload['toolConfig'] = {'functionCallingConfig': {'mode': 'AUTO'}}

                        function_calls = []
                        model_response_parts = []
                        segment_text = ""
                        stream_success = False
                        last_error_message = gemini_user_error_message()
                        fatal_api_error = False

                        for target_model in models_to_try:
                            stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:streamGenerateContent?key={api_key}&alt=sse"
                            for attempt in range(3):
                                try:
                                    generation_calls += 1
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
                                                            if ttft is None:
                                                                ttft = time.time() - request_start_time
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
                                        error_details = extract_gemini_error(resp, api_key)
                                        last_error_message = gemini_user_error_message(
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
                                        error_details = extract_gemini_error(resp, api_key)
                                        last_error_message = gemini_user_error_message(
                                            status_code=error_details.get('status_code'),
                                            error_status=error_details.get('status'),
                                            error_message=error_details.get('message') or error_details.get('raw'),
                                        )
                                        is_config_error = resp.status_code in (401, 403, 404)
                                        err_body = error_details.get('message') or error_details.get('raw')
                                        status_text = error_details.get('status')
                                        status_code = resp.status_code
                                        resp.close()
                                        _logger.error(
                                            "Gemini Stream API returned HTTP %d %s (%s, continuation %d): %s",
                                            status_code, status_text, target_model, continuation_count, (err_body or '')[:300]
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
                                    last_error_message = gemini_user_error_message()
                                    break

                            if stream_success or fatal_api_error:
                                break

                        if not stream_success:
                            yield f"data: {json.dumps({'type': 'error', 'content': last_error_message}, ensure_ascii=False)}\n\n"
                            return

                        if function_calls:
                            tool_calls_count += len(function_calls)
                            _logger.info("ask_stream: Processing %d function_calls", len(function_calls))
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Đang truy vấn cơ sở dữ liệu...'}, ensure_ascii=False)}\n\n"

                            tool_parts = []
                            with odoo.registry(db_name).cursor() as cr:
                                gen_env = odoo.api.Environment(cr, user_id, {})
                                gen_topic = gen_env['topic_chatbot.topic'].browse(topic_id)
                                for fc in function_calls:
                                    func_name = fc.get('name')
                                    func_args = fc.get('args', {})
                                    if llm_provider == 'hybrid':
                                        result = self._execute_hybrid_gemini_tool(
                                            func_name,
                                            func_args,
                                            gen_env,
                                            gen_topic,
                                            hybrid_query_context,
                                        )
                                    else:
                                        result = self._execute_tool(func_name, func_args, gen_env, gen_topic)
                                        if func_name == 'query_odoo_data' and func_args.get('model') in ('decision_documents', 'decision.document') and isinstance(result, dict) and result.get('records'):
                                            document_query_results.append(result)
                                    result, attachment = self._detach_generated_diagram(result)
                                    if attachment:
                                        generated_diagram = attachment
                                    function_response = {
                                        'name': func_name,
                                        'response': {'result': result}
                                    }
                                    if fc.get('id'):
                                        function_response['id'] = fc.get('id')
                                    tool_parts.append({'functionResponse': function_response})

                            valid_model_parts = [p for p in model_response_parts if not ('text' in p and not p.get('text'))]
                            if not valid_model_parts:
                                valid_model_parts = model_response_parts if model_response_parts else [{'functionCall': fc} for fc in function_calls]

                            local_contents.append({'role': 'model', 'parts': valid_model_parts})
                            local_contents.append({'role': 'user', 'parts': tool_parts})
                            continuation_count += 1
                            yield f"data: {json.dumps({'type': 'status', 'content': 'Đang tổng hợp câu trả lời...'}, ensure_ascii=False)}\n\n"
                        else:
                            break

                if not final_reply:
                    final_reply = "Chưa nhận được câu trả lời từ mô hình AI. Vui lòng thử lại."
                    yield f"data: {json.dumps({'type': 'token', 'content': final_reply}, ensure_ascii=False)}\n\n"

                total_time = time.time() - request_start_time
                ttft_str = f"{ttft:.2f}s" if ttft is not None else "N/A"
                prompt_eval_str = f"{prompt_eval_duration:.2f}s" if prompt_eval_duration > 0 else "N/A"
                if llm_provider == 'ollama':
                    active_model = ollama_model
                elif llm_provider == 'openai':
                    active_model = pipeline_data.get('openai_model') or 'gpt-4o-mini'
                else:
                    active_model = clean_model

                _logger.info(
                    "\n[CHAT_PERF_TRACE]\n"
                    "provider = %s\n"
                    "model = %s\n"
                    "probe_calls = %d\n"
                    "generation_calls = %d\n"
                    "tool_calls = %d\n"
                    "ttft = %s\n"
                    "prompt_eval_duration = %s\n"
                    "total_time = %.2fs",
                    llm_provider,
                    active_model,
                    probe_calls,
                    generation_calls,
                    tool_calls_count,
                    ttft_str,
                    prompt_eval_str,
                    total_time
                )

                conv_name = ''
                diagram_done_payload = None
                try:
                    with odoo.registry(db_name).cursor() as cr:
                        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                        fresh_topic = env['topic_chatbot.topic'].browse(topic_id)
                        final_reply = self._append_missing_document_rows(final_reply, document_query_results)
                        sanitized_reply = sanitize_technical_terms(final_reply, topic=fresh_topic)
                        sanitized_reply = normalize_step_lists(sanitized_reply)
                        if sanitized_reply:
                            sanitized_reply = re.sub(r'-{10,}', '----------', sanitized_reply)
                            sanitized_reply = re.sub(r' {10,}', ' ', sanitized_reply)
                        else:
                            sanitized_reply = final_reply

                        message_values = {
                            'conversation_id': conversation_id,
                            'role': 'model',
                            'content': sanitized_reply
                        }
                        if generated_diagram:
                            message_values.update(generated_diagram)
                        msg = env['topic_chatbot.message'].create(message_values)

                        # Copy attachment metadata while this cursor is still open.
                        # Keeping the ``msg`` recordset outside this context causes
                        # Odoo to fetch its fields through an already-closed cursor
                        # when the final SSE event is built.
                        if generated_diagram:
                            diagram_done_payload = {
                                'attachment_name': msg.attachment_name,
                                'attachment_mimetype': msg.attachment_mimetype,
                                'attachment_url': f'/topic_chatbot/message_attachment/{msg.id}',
                            }

                        conv = env['topic_chatbot.conversation'].browse(conversation_id)
                        if conv.name in ('New Chat', 'Cuộc trò chuyện mới') and len(message) > 0:
                            new_name = message[:40] + ('...' if len(message) > 40 else '')
                            conv.write({'name': new_name})
                        conv_name = conv.name or ''
                        env.flush_all()
                        cr.commit()
                        _logger.info("ask_stream: Successfully saved bot reply (id=%s) for conv %s", msg.id, conversation_id)
                except Exception as e_save:
                    _logger.error("ask_stream: FAILED to save bot message to DB: %s", str(e_save), exc_info=True)

                done_payload = {'type': 'done', 'conversation_name': conv_name}
                if diagram_done_payload:
                    done_payload.update(diagram_done_payload)
                yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

            finally:
                try:
                    with odoo.registry(db_name).cursor() as cr:
                        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                        conv = env['topic_chatbot.conversation'].browse(conversation_id)
                        if conv.exists():
                            conv.write({'is_processing': False})
                        env.flush_all()
                        cr.commit()
                except Exception as ex:
                    _logger.error("Failed to reset is_processing status: %s", str(ex))

        headers = {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
        return werkzeug.Response(generate(), headers=headers, mimetype='text/event-stream')
