# -*- coding: utf-8 -*-
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
from .rag_engine import retrieve_context

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

    def _execute_tool(self, func_name, func_args, env, topic):
        """Execute a tool/function call (query_odoo_data or query_sql_server_data)."""
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
        return {'error': f"Unknown function '{func_name}'"}

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

        params = env['ir.config_parameter'].sudo()
        llm_provider = params.get_param('topic_chatbot.llm_provider', default='gemini') or 'gemini'
        ollama_url = (params.get_param('topic_chatbot.ollama_url') or 'http://localhost:11434').rstrip('/')
        ollama_chat_model = params.get_param('topic_chatbot.ollama_chat_model', default='qwen2.5:14b') or 'qwen2.5:14b'

        api_key = params.get_param('topic_chatbot.gemini_api_key')
        raw_model = params.get_param('topic_chatbot.gemini_model', default='gemini-3.6-flash')
        model = normalize_model_name(raw_model)

        if llm_provider == 'gemini' and not api_key:
            return None, {'error': 'Chưa cấu hình Gemini API Key. Vui lòng vào menu Cấu hình để nhập API Key.'}

        rewriter_res = rewrite_search_query(env, message, conversation.id, api_key, model)
        route_reason = "Không xác định"
        if len(rewriter_res) >= 6:
            search_query, filters, is_valid, route_type, structured_query, route_reason = rewriter_res[:6]
        elif len(rewriter_res) == 5:
            search_query, filters, is_valid, route_type, structured_query = rewriter_res
        else:
            search_query, filters, is_valid, route_type = rewriter_res[:4]
            structured_query = message if route_type == 'STRUCTURED_DATA' else None

        chunks = retrieve_context(
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
        has_documents = bool(topic.document_ids)
        document_names = [d.name for d in topic.document_ids if d.name]

        is_mssql_active = bool(
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
                is_db_query=topic.is_db_query,
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
                is_db_query=topic.is_db_query,
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
        if topic.is_db_query:
            tools_list.append({
                'name': 'query_odoo_data',
                'description': (
                    'Truy vấn đọc dữ liệu (Read-only) an toàn từ database Odoo '
                    'để tìm thông tin liên quan đến các dữ liệu nghiệp vụ: Nhân viên, '
                    'Phòng ban, Kết quả KPI tháng, Đánh giá KPI của lãnh đạo, KPI năm.\n'
                    'CHỈ sử dụng công cụ này khi người dùng hỏi các câu hỏi thực tế về dữ liệu '
                    'hệ thống Odoo (như KPI của một ai đó, xếp loại phòng ban, danh sách nhân viên, v.v.).\n'
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
                                '"kpi_month_report", "kpi_year_results".'
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

        tools = [{'functionDeclarations': tools_list}] if tools_list else None

        pipeline_data = {
            'llm_provider': llm_provider,
            'ollama_url': ollama_url,
            'ollama_chat_model': ollama_chat_model,
            'api_key': api_key,
            'model': model,
            'context_str': context_str,
            'system_instruction': system_instruction,
            'contents': contents,
            'tools': tools,
            'tools_list': tools_list,
            'topic': topic,
            'search_query': search_query,
        }
        return pipeline_data, None

    def handle_ask(self, conversation_id, message):
        """Synchronous chat processing (/topic_chatbot/ask)."""
        env = self.env
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
        try:
            # Save user message
            env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'user',
                'content': message
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
                        'options': {'temperature': 0.0, 'num_predict': 4096}
                    }
                    if ollama_tools:
                        ollama_payload['tools'] = ollama_tools

                    response = requests.post(f"{ollama_url}/api/chat", json=ollama_payload, timeout=120)
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

                            if func_name == 'query_odoo_data':
                                result = execute_odoo_query(
                                    model=func_args.get('model'),
                                    domain=func_args.get('domain'),
                                    fields=func_args.get('fields'),
                                    env=env
                                )
                            elif func_name == 'query_sql_server_data':
                                result = execute_mssql_query(
                                    sql_query=func_args.get('sql_query'),
                                    topic=topic,
                                    env=env
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
            active_model = ollama_model if llm_provider == 'ollama' else (model or 'gemini-3.6-flash')

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
            reply_text = sanitize_technical_terms(reply_text, topic=topic)
            reply_text = normalize_step_lists(reply_text)
            if reply_text:
                reply_text = re.sub(r'-{10,}', '----------', reply_text)
                reply_text = re.sub(r' {10,}', ' ', reply_text)

            env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'model',
                'content': reply_text
            })
            bot_reply_saved = True

            if conversation.name in ('New Chat', 'Cuộc trò chuyện mới') and len(message) > 0:
                new_name = message[:40] + ('...' if len(message) > 40 else '')
                conversation.write({'name': new_name})

            env.flush_all()
            env.cr.commit()

            return {
                'response': reply_text,
                'conversation_name': conversation.name
            }

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
            if not bot_reply_saved:
                try:
                    orphan = env['topic_chatbot.message'].search([
                        ('conversation_id', '=', conversation.id),
                        ('role', '=', 'user'),
                    ], order='create_date desc, id desc', limit=1)
                    if orphan:
                        orphan.unlink()
                except Exception as e_orph:
                    _logger.error("Failed to clean up orphan message: %s", str(e_orph))
            conversation.sudo().write({'is_processing': False})

    def handle_ask_stream(self, httprequest_data):
        """Streaming chat processing with SSE (/topic_chatbot/ask_stream)."""
        data = json.loads(httprequest_data)
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

        env['topic_chatbot.message'].create({
            'conversation_id': conversation.id,
            'role': 'user',
            'content': message
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
            continuation_count = 0
            max_continuations = 4
            clean_model = model or 'gemini-3.6-flash'

            models_to_try = [clean_model]
            if clean_model != 'gemini-3.5-flash-lite':
                models_to_try.append('gemini-3.5-flash-lite')

            req_headers = {'Content-Type': 'application/json'}
            local_contents = list(contents)

            try:
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
                                'options': {'temperature': 0.0, 'num_predict': 4096},
                                'tools': ollama_tools
                            }
                            probe_resp = requests.post(f"{ollama_url}/api/chat", json=probe_payload, timeout=90)
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
                            'options': {'temperature': 0.0, 'num_predict': 4096}
                        }
                        try:
                            stream_resp = requests.post(
                                f"{ollama_url}/api/chat",
                                json=stream_payload,
                                stream=True,
                                timeout=180
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
                else:
                    while continuation_count <= max_continuations:
                        payload = {
                            'contents': local_contents,
                            'systemInstruction': {'parts': [{'text': system_instruction}]},
                            'generationConfig': {'maxOutputTokens': 8192, 'temperature': 0.0}
                        }
                        if tools:
                            payload['tools'] = tools
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
                                    if func_name == 'query_odoo_data':
                                        result = execute_odoo_query(
                                            model=func_args.get('model'),
                                            domain=func_args.get('domain'),
                                            fields=func_args.get('fields'),
                                            env=gen_env
                                        )
                                    elif func_name == 'query_sql_server_data':
                                        sql_query = func_args.get('sql_query', '')
                                        safe_query = sql_query.encode('ascii', 'backslashreplace').decode('ascii') if sql_query else ''
                                        _logger.info("ask_stream: Gemini called query_sql_server_data with query: %s", safe_query)
                                        result = execute_mssql_query(
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
                    final_reply = "Đã tra cứu thành công dữ liệu từ SQL Server nhưng không nhận được phản hồi tổng hợp từ AI. Vui lòng thử lại."
                    yield f"data: {json.dumps({'type': 'token', 'content': final_reply}, ensure_ascii=False)}\n\n"

                total_time = time.time() - request_start_time
                ttft_str = f"{ttft:.2f}s" if ttft is not None else "N/A"
                prompt_eval_str = f"{prompt_eval_duration:.2f}s" if prompt_eval_duration > 0 else "N/A"
                active_model = ollama_model if llm_provider == 'ollama' else clean_model

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
                try:
                    with odoo.registry(db_name).cursor() as cr:
                        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                        fresh_topic = env['topic_chatbot.topic'].browse(topic_id)
                        sanitized_reply = sanitize_technical_terms(final_reply, topic=fresh_topic)
                        sanitized_reply = normalize_step_lists(sanitized_reply)
                        if sanitized_reply:
                            sanitized_reply = re.sub(r'-{10,}', '----------', sanitized_reply)
                            sanitized_reply = re.sub(r' {10,}', ' ', sanitized_reply)
                        else:
                            sanitized_reply = final_reply

                        msg = env['topic_chatbot.message'].create({
                            'conversation_id': conversation_id,
                            'role': 'model',
                            'content': sanitized_reply
                        })

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

                yield f"data: {json.dumps({'type': 'done', 'conversation_name': conv_name}, ensure_ascii=False)}\n\n"

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
