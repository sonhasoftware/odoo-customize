# -*- coding: utf-8 -*-
from odoo import api, fields, models

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
    sequence = fields.Integer(
        string='Chunk Number',
        default=1,
        index=True,
        help="Order of this text chunk within the source document."
    )
    content = fields.Text(string='Content', required=True)
    vector_placeholder = fields.Binary(
        string='Vector Embedding Placeholder',
        help="Placeholder for future integration with Vector search (e.g. pgvector or numpy arrays)."
    )

    @api.model
    def _create_fts_index(self):
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_content_fts_index
            ON topic_chatbot_chunk
            USING GIN (to_tsvector('simple', content))
        """)
