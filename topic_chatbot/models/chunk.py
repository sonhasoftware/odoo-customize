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
    embedding = fields.Text(
        string='Vector Embedding JSON',
        help="JSON string storing the floating point vector embedding array for Semantic Search."
    )
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

    @api.model
    def _auto_init(self):
        res = super(TopicChatbotChunk, self)._auto_init()
        # Create FTS index
        self._create_fts_index()
        # Initialize pgvector
        try:
            self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            self.env.cr.execute("""
                ALTER TABLE topic_chatbot_chunk 
                ADD COLUMN IF NOT EXISTS embedding_vector vector(768);
            """)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_embedding_idx
                ON topic_chatbot_chunk USING hnsw (embedding_vector vector_cosine_ops);
            """)
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error("Failed to initialize pgvector on topic_chatbot_chunk: %s", str(e))
            self.env.cr.rollback()
        return res

    @api.model
    def _generate_embedding(self, text, api_key, model_name='gemini-embedding-2'):
        """Generate text vector embedding via Gemini Embedding API with automatic model fallback."""
        import json
        import requests
        import logging

        _logger = logging.getLogger(__name__)

        if not text or not api_key:
            return None

        # Clean redundant 'models/' prefix to avoid double 'models/models/' in URL
        clean_model = (model_name or 'gemini-embedding-2').replace('models/', '').strip()
        if clean_model in ('text-embedding-004', 'embedding-001'):
            clean_model = 'gemini-embedding-2'
        models_to_try = [clean_model]

        headers = {'Content-Type': 'application/json'}

        for m_name in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:embedContent?key={api_key}"
            payload = {
                "model": f"models/{m_name}",
                "content": {
                    "parts": [{"text": text}]
                }
            }

            try:
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                if res.status_code == 404 and m_name != models_to_try[-1]:
                    _logger.warning("Gemini embedding model '%s' returned 404, attempting fallback to '%s'", m_name, models_to_try[-1])
                    continue
                res.raise_for_status()
                res_json = res.json()
                values = res_json.get('embedding', {}).get('values', [])
                if values:
                    return json.dumps(values)
            except Exception as e:
                err_msg = str(e)
                if api_key:
                    err_msg = err_msg.replace(api_key, "REDACTED")
                _logger.warning("Failed to generate embedding via Gemini API (%s): %s", m_name, err_msg)

        return None
