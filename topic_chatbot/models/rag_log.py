# -*- coding: utf-8 -*-
from odoo import fields, models

class TopicChatbotRagLog(models.Model):
    _name = 'topic_chatbot.rag_log'
    _description = 'RAG Retrieval & Prompt Context Log'
    _order = 'create_date desc'

    topic_id = fields.Many2one(
        'topic_chatbot.topic',
        string='Topic',
        ondelete='set null',
        index=True
    )
    topic_name = fields.Char(string='Topic Name')
    conversation_id = fields.Many2one(
        'topic_chatbot.conversation',
        string='Conversation',
        ondelete='set null',
        index=True
    )
    user_query = fields.Text(string='User Query', required=True)
    rewritten_query = fields.Text(string='Rewritten Query')
    route_type = fields.Char(string='Intent / Route', index=True)
    route_reason = fields.Text(string='Route Reason')
    tier_activated = fields.Char(string='RAG Tier Activated', index=True)
    tier_reason = fields.Text(string='Tier Reason')
    retrieval_method = fields.Char(string='Retrieval Method')
    retrieved_chunks_count = fields.Integer(string='Chunks Retrieved')
    retrieved_chunks_summary = fields.Text(string='Chunks Summary (JSON)')
    prompt_context = fields.Text(string='Prompt Context Sent to LLM')
    full_payload = fields.Text(string='Full Payload JSON')
    create_date = fields.Datetime(string='Created On', readonly=True, index=True)
