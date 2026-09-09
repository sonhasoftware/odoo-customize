# -*- coding: utf-8 -*-
import logging
from odoo import http
from odoo.http import request

from ..utils.security_utils import (
    DEPRECATED_GEMINI_MODEL_MAP,
    normalize_model_name,
    redact_api_key,
    extract_gemini_error,
    gemini_user_error_message,
)
from ..services.rate_limiter import (
    RATE_LIMIT_MAX_MESSAGES,
    RATE_LIMIT_WINDOW_SECONDS,
    check_rate_limit,
)
from ..services.prompt_builder import (
    build_system_instruction,
    sanitize_technical_terms,
)
from ..services.sql_engine import (
    execute_odoo_query,
    execute_mssql_query,
)
from ..services.query_rewriter import (
    rewrite_search_query,
    should_use_hyde,
    generate_hypothetical_document,
)
from ..services.rag_engine import (
    retrieve_context,
)
from ..services.chat_service import ChatService

_logger = logging.getLogger(__name__)


class TopicChatbotController(http.Controller):
    """Thin HTTP Controller for Topic Chatbot endpoints."""

    DEPRECATED_GEMINI_MODEL_MAP = DEPRECATED_GEMINI_MODEL_MAP
    RATE_LIMIT_MAX_MESSAGES = RATE_LIMIT_MAX_MESSAGES
    RATE_LIMIT_WINDOW_SECONDS = RATE_LIMIT_WINDOW_SECONDS

    # ---------------------------------------------------------
    # Backward Compatibility Wrappers & Delegation Methods
    # ---------------------------------------------------------
    def _normalize_model_name(self, model):
        return normalize_model_name(model)

    def _check_rate_limit(self, env, user_id):
        return check_rate_limit(env, user_id, self.RATE_LIMIT_MAX_MESSAGES, self.RATE_LIMIT_WINDOW_SECONDS)

    def _redact_api_key(self, value, api_key):
        return redact_api_key(value, api_key)

    def _extract_gemini_error(self, response, api_key=None):
        return extract_gemini_error(response, api_key)

    def _gemini_user_error_message(self, status_code=None, error_status='', error_message=''):
        return gemini_user_error_message(status_code, error_status, error_message)

    def _build_system_instruction(
        self,
        context_str,
        topic_name="",
        topic_description="",
        other_topic_names=None,
        document_names=None,
        is_db_query=False,
        is_mssql_query=False,
        mssql_tables="",
        has_documents=False
    ):
        return build_system_instruction(
            context_str,
            topic_name=topic_name,
            topic_description=topic_description,
            other_topic_names=other_topic_names,
            document_names=document_names,
            is_db_query=is_db_query,
            is_mssql_query=is_mssql_query,
            mssql_tables=mssql_tables,
            has_documents=has_documents
        )

    def _sanitize_technical_terms(self, text, topic=None):
        return sanitize_technical_terms(text, topic=topic)

    def _execute_odoo_query(self, model, domain=None, fields=None, env=None):
        return execute_odoo_query(model, domain=domain, fields=fields, env=env)

    def _execute_mssql_query(self, sql_query, topic=None, env=None):
        return execute_mssql_query(sql_query, topic=topic, env=env)

    def _rewrite_search_query(self, message, conversation_id, api_key, model):
        return rewrite_search_query(request.env, message, conversation_id, api_key, model)

    def _should_use_hyde(self, message):
        return should_use_hyde(message)

    def _generate_hypothetical_document(self, query, api_key, model=None):
        return generate_hypothetical_document(request.env, query, api_key, model)

    def _retrieve_context(self, topic_id, message, limit=15, filters=None, original_query=None, is_valid=True, route_type='SEMANTIC_RAG'):
        return retrieve_context(request.env, topic_id, message, limit=limit, filters=filters, original_query=original_query, is_valid=is_valid, route_type=route_type)

    # ---------------------------------------------------------
    # HTTP Routes
    # ---------------------------------------------------------
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
        conversation = request.env['topic_chatbot.conversation'].search([
            ('id', '=', conversation_id_int),
            ('user_id', '=', request.env.uid)
        ], limit=1)
        if not conversation:
            return []

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

    @http.route('/topic_chatbot/ask', type='json', auth='user')
    def ask(self, conversation_id, message):
        """Send message to Gemini API with RAG context and Odoo Tools (Synchronous JSON)."""
        chat_service = ChatService(request.env)
        return chat_service.handle_ask(conversation_id, message)

    @http.route('/topic_chatbot/ask_stream', type='http', auth='user', csrf=False, methods=['POST'])
    def ask_stream(self):
        """Send message to Gemini API with streaming SSE response."""
        chat_service = ChatService(request.env)
        return chat_service.handle_ask_stream(request.httprequest.data)
