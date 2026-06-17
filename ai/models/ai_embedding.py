# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging

from odoo import api, fields, models, _
from requests.exceptions import RequestException
from odoo.tools import SQL
from odoo.exceptions import UserError

from odoo.addons.ai.orm.field_vector import Vector
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai.utils.llm_providers import EMBEDDING_MODELS_SELECTION, get_provider_for_embedding_model

_logger = logging.getLogger(__name__)


class AIEmbedding(models.Model):
    _name = 'ai.embedding'
    _description = "Attachment Chunks Embedding"
    _order = 'sequence'

    attachment_id = fields.Many2one(
        'ir.attachment',
        string="Attachment",
        required=True,
        ondelete='cascade'
    )
    checksum = fields.Char(related='attachment_id.checksum')
    sequence = fields.Integer(string="Sequence", default=10)
    content = fields.Text(string="Chunk Content", required=True)
    embedding_model = fields.Selection(selection=EMBEDDING_MODELS_SELECTION, string="Embedding Model", required=True)
    has_embedding_generation_failed = fields.Boolean(string="Has Embedding Generation Failed", default=False)
    embedding_vector = Vector(size=1536)
    def init(self):
        super().init()
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute("""
                    CREATE INDEX IF NOT EXISTS ai_embedding_vector_idx 
                    ON ai_embedding USING ivfflat (embedding_vector vector_cosine_ops)
                """)
        except Exception as e:
            _logger.warning("Could not create index on embedding_vector. Please ensure pgvector extension is installed in PostgreSQL. Error: %s", e)

    @api.model
    def _get_dimensions(self):
        return self._fields['embedding_vector'].size

    @api.model
    def _get_similar_chunks(self, query_embedding, sources, embedding_model, top_n=5):
        active_sources = sources.filtered(lambda s: s.is_active and s.user_has_access)
        if not active_sources:
            return self

        attachment_ids = active_sources.mapped('attachment_id').ids
        target_checksums = self.env['ir.attachment'].browse(attachment_ids).mapped('checksum')
        # Execute the SQL query to find similar embeddings of the same sources' attachments checksum
        query = SQL(
            '''
                SELECT
                    ai_embedding.id,
                    1 - (embedding_vector <=> %s::vector) AS similarity
                FROM ai_embedding
                INNER JOIN ir_attachment ON ir_attachment.id = ai_embedding.attachment_id
                WHERE ir_attachment.checksum = ANY(%s) AND ai_embedding.embedding_model = %s
                ORDER BY similarity DESC
                LIMIT %s;
            ''',
            query_embedding, target_checksums, embedding_model, top_n
        )
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()

        # Enforce similarity threshold to avoid loading irrelevant context (e.g. for greetings like "hello")
        # Google's gemini-embedding-001 has high baseline similarity (around 0.55-0.60 for unrelated queries)
        if embedding_model and embedding_model.startswith('gemini'):
            threshold = 0.65
        else:
            threshold = 0.40

        similar_ids = [id_ for id_, similarity in results if similarity >= threshold]
        return self.browse(similar_ids)

    @api.model
    def _cron_generate_embedding(self, batch_size=100):
        """
        Generate embeddings for sources, handling multiple embedding models per source.
        """

        # Create embedding chunks for sources that are processing and have an attachment
        # and that don't have any embedding chunks yet
        processing_sources = self.env['ai.agent.source'].search([
            ('status', '=', 'processing'),
            ('attachment_id', '!=', False),
        ])
        if processing_sources:
            existing_embeddings_grouped = self._read_group(
                domain=[],
                groupby=['attachment_id', 'embedding_model'],
            )
            existing_checksum_model_pairs = [
                (attachment.checksum, embedding_model)
                for attachment, embedding_model in existing_embeddings_grouped
                if attachment
            ]
            for source in processing_sources:
                embedding_model = source.agent_id._get_embedding_model()
                if (source.attachment_id.checksum, embedding_model) not in existing_checksum_model_pairs:
                    _logger.info("Creating embedding chunks for source %s", source.name)
                    content = source.attachment_id._get_attachment_content()
                    if not content:
                        source.write({
                            'status': 'failed',
                            'error_details': _("Invalid attachment. Failed to extract content."),
                        })
                        continue
                    source.attachment_id._setup_attachment_chunks(embedding_model, content)

        # Generate embeddings for sources that are missing embeddings
        missing_embeddings = self.search([
            ("embedding_vector", "=", False),
            ("has_embedding_generation_failed", "=", False)
        ], limit=batch_size)
        staged_sources = self.env['ai.agent.source'].search([
            ('attachment_id.checksum', 'in', missing_embeddings.mapped('checksum'))
        ])
        _logger.info("Starting embedding update - missing %s embeddings.", len(missing_embeddings))
        cron_model = self.env['ir.cron']
        has_commit_progress = hasattr(cron_model, '_commit_progress')
        if has_commit_progress:
            cron_model._commit_progress(remaining=len(missing_embeddings))
        failed_embeddings = self.env[self._name]

        # Group by embedding_model to batch them
        by_model = {}
        for embedding in missing_embeddings:
            by_model.setdefault(embedding.embedding_model, []).append(embedding)

        for model, embeddings in by_model.items():
            provider = get_provider_for_embedding_model(self.env, model)
            api_service = LLMApiService(env=self.env, provider=provider)
            chunk_batch_size = 20  # Batch size for Gemini/OpenAI embedding calls
            
            for i in range(0, len(embeddings), chunk_batch_size):
                batch = embeddings[i:i + chunk_batch_size]
                try:
                    contents = [emb.content for emb in batch]
                    _logger.info("Computing batch embedding for %s records of model %s", len(batch), model)
                    response = api_service.get_embedding(
                        input=contents,
                        dimensions=self._get_dimensions(),
                        model=model,
                    )
                    
                    data_items = response.get('data', [])
                    if len(data_items) != len(batch):
                        raise ValueError("Mismatch between batch size and response size")
                        
                    for idx, data_item in enumerate(data_items):
                        batch[idx].embedding_vector = data_item['embedding']
                        
                    if has_commit_progress and not cron_model._commit_progress(len(batch)):
                        break
                except Exception as e:
                    _logger.warning("Failed to compute batch embedding: %s. Retrying individually.", e)
                    # If batch fails, fallback to individual processing for this batch
                    for embedding in batch:
                        try:
                            _logger.info("Computing embedding individually for record %s", embedding.id)
                            response = api_service.get_embedding(
                                input=embedding.content,
                                dimensions=self._get_dimensions(),
                                model=model,
                            )
                            embedding.embedding_vector = response['data'][0]['embedding']
                            if has_commit_progress and not cron_model._commit_progress(1):
                                break
                        except (RequestException, UserError):
                            failed_embeddings |= embedding
                            if has_commit_progress:
                                cron_model._commit_progress(1)

        if failed_embeddings:
            failed_embeddings.write({'has_embedding_generation_failed': True})
            if has_commit_progress:
                cron_model._commit_progress(len(failed_embeddings))

        # Handle the status of sources
        for source in staged_sources:
            embedding_model = source.agent_id._get_embedding_model()
            source._update_source_status(embedding_model)

    @api.autovacuum
    def _gc_embeddings(self):
        """
        Autovacuum: Cleanup embedding chunks not associated with any agent's attachments.
        """
        all_agents = self.env['ai.agent'].with_context(active_test=False).search([])
        used_attachment_ids = all_agents.mapped('sources_ids').mapped('attachment_id')
        used_checksums = used_attachment_ids.mapped('checksum')
        unused_chunks = self.search([
            ('checksum', 'not in', used_checksums),
        ])
        if unused_chunks:
            chunk_count = len(unused_chunks)
            _logger.info("Autovacuum: Cleaning up %s unused embedding chunks", chunk_count)
            unused_chunks.unlink()
