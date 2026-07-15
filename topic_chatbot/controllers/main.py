# -*- coding: utf-8 -*-
import json
import logging
import requests
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
            'owner': t.create_uid.name
        } for t in topics]

    @http.route('/topic_chatbot/get_conversations', type='json', auth='user')
    def get_conversations(self, topic_id):
        """Fetch all conversations for a specific topic of the current user."""
        conversations = request.env['topic_chatbot.conversation'].search([
            ('topic_id', '=', int(topic_id)),
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
        # Security check: User must own the conversation
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', int(conversation_id)),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return []

        messages = request.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation.id)
        ])
        return [{
            'id': m.id,
            'role': m.role,
            'content': m.content,
            'create_date': m.create_date
        } for m in messages]

    @http.route('/topic_chatbot/create_conversation', type='json', auth='user')
    def create_conversation(self, topic_id):
        """Create a new conversation for a topic."""
        topic = request.env['topic_chatbot.topic'].browse(int(topic_id))
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
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', int(conversation_id)),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if conversation:
            conversation.unlink()
            return {'success': True}
        return {'error': 'Conversation not found or access denied.'}

    def _execute_odoo_query(self, model, domain=None, fields=None):
        """Execute a safe, read-only Odoo search_read query using the current user's environment."""
        safe_models = [
            'hr.employee', 
            'hr.department', 
            'sonha.kpi.result.month', 
            'report.kpi.month', 
            'sonha.kpi.year'
        ]
        
        if model not in safe_models:
            return {'error': f"Truy cập vào model '{model}' bị hạn chế vì lý do bảo mật."}

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
                    dept = request.env['hr.department'].sudo().search([
                        '|', '|',
                        ('name', 'ilike', val),
                        ('complete_name', 'ilike', val),
                        ('name', 'ilike', val.replace('phòng', '').replace('ban', '').strip())
                    ], limit=1)
                    if dept:
                        clean_domain.append([field, '=', dept.id])
                        continue
                    else:
                        return {'error': f"Không tìm thấy phòng ban nào khớp với tên '{val}'."}
                elif field == 'employee_id' and isinstance(val, str):
                    emp = request.env['hr.employee'].sudo().search([
                        ('name', 'ilike', val)
                    ], limit=1)
                    if emp:
                        clean_domain.append([field, '=', emp.id])
                        continue
                    else:
                        return {'error': f"Không tìm thấy nhân viên nào có tên '{val}'."}
            clean_domain.append(term)

        try:
            records = request.env[model].search_read(clean_domain, fields or [], limit=80)
            cleaned_records = []
            for rec in records:
                clean_rec = {}
                for k, v in rec.items():
                    if isinstance(v, tuple) and len(v) == 2:
                        clean_rec[k] = v[1]
                    else:
                        clean_rec[k] = v
                cleaned_records.append(clean_rec)
            return cleaned_records
        except Exception as e:
            return {'error': f"Lỗi truy vấn Odoo ORM: {str(e)}"}

    @http.route('/topic_chatbot/ask', type='json', auth='user')
    def ask(self, conversation_id, message):
        """Send message to Gemini API with RAG context and Odoo Tools."""
        # 1. Fetch conversation & check ownership
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', int(conversation_id)),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return {'error': 'Conversation not found or access denied.'}

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
        context_str = "\n\n".join([f"--- Đoạn tài liệu {i+1} ---\n{chunk}" for i, chunk in enumerate(chunks)])
        
        system_instruction = (
            "Bạn là một trợ lý AI thông minh kết nối dữ liệu tài liệu (RAG) và cơ sở dữ liệu Odoo.\n"
            "NHIỆM VỤ CỦA BẠN:\n"
            "1. ĐỐI VỚI DỮ LIỆU ODOO (KPI, NHÂN VIÊN, PHÒNG BAN): Khi người dùng hỏi về dữ liệu thực tế trên hệ thống Odoo (ví dụ: kết quả KPI phòng ban, danh sách nhân viên, thông tin phòng ban...), bạn BẮT BUỘC phải sử dụng công cụ 'query_odoo_data' để truy vấn cơ sở dữ liệu. Sau khi nhận được dữ liệu, hãy phân tích và tổng hợp câu trả lời chính xác, trung thực và chuyên nghiệp.\n"
            "2. ĐỐI VỚI TÀI LIỆU RAG: Nếu người dùng hỏi các câu hỏi chuyên môn, tài liệu quy trình được cung cấp dưới đây, bạn hãy trả lời bám sát theo thông tin trong tài liệu đó.\n"
            "3. ĐỐI VỚI CÂU HỎI THƯỜNG: Nếu người dùng chào hỏi, hỏi kiến thức chung..., bạn tự do sử dụng kiến thức rộng lớn của mình để trả lời.\n"
            "4. Câu trả lời của bạn phải viết bằng tiếng Việt tự nhiên, lịch sự và mạch lạc.\n\n"
            f"NỘI DUNG TÀI LIỆU THAM KHẢO (NẾU CÓ):\n{context_str}"
        )

        # 5. Fetch API Credentials
        params = request.env['ir.config_parameter'].sudo()
        api_key = params.get_param('topic_chatbot.gemini_api_key')
        model = params.get_param('topic_chatbot.gemini_model', default='gemini-1.5-flash')

        if not api_key:
            error_msg = "Chưa cấu hình Gemini API Key. Vui lòng liên hệ Administrator để thiết lập trong Cấu hình."
            request.env['topic_chatbot.message'].create({
                'conversation_id': conversation.id,
                'role': 'model',
                'content': error_msg
            })
            return {'response': error_msg}

        # 6. Format chat history for Gemini API
        db_messages = request.env['topic_chatbot.message'].search([
            ('conversation_id', '=', conversation.id)
        ])
        
        contents = []
        for m in db_messages:
            contents.append({
                'role': 'user' if m.role == 'user' else 'model',
                'parts': [{'text': m.content}]
            })

        # 7. Define Gemini Tools for Database Query
        tools = [{
            'function_declarations': [
                {
                    'name': 'query_odoo_data',
                    'description': (
                        'Truy vấn đọc dữ liệu (Read-only) an sau từ database Odoo '
                        'để tìm thông tin liên quan đến các bảng: hr.employee (Nhân viên), '
                        'hr.department (Phòng ban), sonha.kpi.result.month (Kết quả KPI tháng), '
                        'report.kpi.month (Đánh giá KPI của lãnh đạo), sonha.kpi.year (KPI năm).\n'
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
                }
            ]
        }]

        # 8. Request to Gemini API with Tool Loop
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            'contents': contents,
            'systemInstruction': {
                'parts': [{'text': system_instruction}]
            },
            'tools': tools,
            'generationConfig': {
                'temperature': 0.1,
                'maxOutputTokens': 2048
            }
        }

        reply_text = ""
        api_call_count = 0
        try:
            while api_call_count < 3:
                response = requests.post(url, headers=headers, json=payload, timeout=45)
                response.raise_for_status()
                res_data = response.json()
                
                # Check for functionCall
                function_call = None
                if 'candidates' in res_data and len(res_data['candidates']) > 0:
                    candidate = res_data['candidates'][0]
                    if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                        part = candidate['content']['parts'][0]
                        if 'functionCall' in part:
                            function_call = part['functionCall']
                
                if function_call:
                    func_name = function_call.get('name')
                    func_args = function_call.get('args', {})
                    
                    # Execute local function
                    if func_name == 'query_odoo_data':
                        result = self._execute_odoo_query(
                            model=func_args.get('model'),
                            domain=func_args.get('domain'),
                            fields=func_args.get('fields')
                        )
                    else:
                        result = {'error': f"Unknown function '{func_name}'"}
                    
                    # Append functionCall and functionResponse to contents history
                    contents.append({
                        'role': 'model',
                        'parts': [{'functionCall': function_call}]
                    })
                    contents.append({
                        'role': 'tool',
                        'parts': [{
                            'functionResponse': {
                                'name': func_name,
                                'response': {'result': result}
                            }
                        }]
                    })
                    
                    payload['contents'] = contents
                    api_call_count += 1
                else:
                    # No functionCall, extract final text response
                    if 'candidates' in res_data and len(res_data['candidates']) > 0:
                        candidate = res_data['candidates'][0]
                        if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                            reply_text = candidate['content']['parts'][0].get('text', '')
                    
                    if not reply_text:
                        reply_text = "Không nhận được phản hồi hợp lệ từ Gemini API."
                    break

        except Exception as e:
            _logger.error("Error communicating with Gemini API: %s", str(e))
            reply_text = f"Đã xảy ra lỗi khi kết nối tới AI: {str(e)}"

        # 9. Save bot's reply
        request.env['topic_chatbot.message'].create({
            'conversation_id': conversation.id,
            'role': 'model',
            'content': reply_text
        })

        # 10. Update Conversation Name if it's default
        if conversation.name == 'New Chat' and len(message) > 0:
            new_name = message[:40] + ('...' if len(message) > 40 else '')
            conversation.write({'name': new_name})

        return {
            'response': reply_text,
            'conversation_name': conversation.name
        }

    def _retrieve_context(self, topic_id, message, limit=5):
        """Retrieve relevant chunks using simple search + Python fallback."""
        # 1. Attempt PostgreSQL tsvector text search
        try:
            # simple configuration splits words and checks for matching tokens
            sql_query = """
                SELECT id, content FROM topic_chatbot_chunk
                WHERE topic_id = %s AND to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
                LIMIT %s
            """
            request.env.cr.execute(sql_query, (topic_id, message, limit))
            results = request.env.cr.fetchall()
            if results:
                return [r[1] for r in results]
        except Exception as e:
            _logger.warning("Postgres tsvector search failed, falling back to python match: %s", str(e))

        # 2. Python-based token score matching (Fallback)
        chunks = request.env['topic_chatbot.chunk'].search([('topic_id', '=', topic_id)])
        if not chunks:
            return []

        # Tokenize query
        words = [w.lower() for w in message.split() if len(w) > 1]
        if not words:
            return [c.content for c in chunks[:limit]]

        scored_chunks = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            score = sum(content_lower.count(word) for word in words)
            if score > 0:
                scored_chunks.append((score, chunk))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [item[1].content for item in scored_chunks[:limit]]
