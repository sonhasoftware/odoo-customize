# -*- coding: utf-8 -*-
from odoo import fields, models

class TopicChatbotChunk(models.Model):
    _name = 'topic_chatbot.chunk'
    _description = 'Document Text Chunk'

    topic_id = fields.Many2one(
        'topic_chatbot.topic', 
        string='Topic', 
        required=True, 
        ondelete='cascade'
    )
    document_id = fields.Many2one(
        'topic_chatbot.document', 
        string='Document', 
        required=True, 
        ondelete='cascade'
    )
    content = fields.Text(string='Content', required=True)
    vector_placeholder = fields.Binary(
        string='Vector Embedding Placeholder',
        help="Placeholder for future integration with Vector search (e.g. pgvector or numpy arrays)."
    )
