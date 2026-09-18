# -*- coding: utf-8 -*-
import json
import logging
import time
import requests
from odoo import api, fields, models
from ..services import embedding_service

_logger = logging.getLogger(__name__)

# ==============================================================================
# Centralized Embedding Constants (Single Source of Truth for Embedding Model)
# ==============================================================================
DEFAULT_EMBEDDING_MODEL = 'gemini-embedding-2'
EMBEDDING_BATCH_SIZE = 50
PROACTIVE_BATCH_DELAY_SECONDS = 1.5
MAX_RETRY_ATTEMPTS = 4
BACKOFF_DELAYS = [6.0, 15.0, 35.0, 60.0]
OLLAMA_COMPUTE_LOCK_KEY = 830917


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
    parent_id = fields.Many2one(
        'topic_chatbot.chunk',
        string='Parent Chunk',
        ondelete='cascade',
        index=True,
        help="Reference to the parent (large context) chunk. Child chunks are used for precise search, parent chunks provide full context."
    )
    child_ids = fields.One2many(
        'topic_chatbot.chunk',
        'parent_id',
        string='Child Chunks'
    )
    chunk_type = fields.Selection([
        ('standard', 'Standard'),
        ('parent', 'Parent Context Chunk'),
        ('child', 'Child Search Chunk'),
    ], string='Chunk Type', default='standard', index=True)
    content = fields.Text(string='Content', required=True)
    embedding = fields.Text(
        string='Vector Embedding JSON',
        help="JSON string storing the floating point vector embedding array for Semantic Search."
    )
    embedding_ollama = fields.Text(
        string='Ollama Vector Embedding JSON',
        help="JSON string storing the floating point vector embedding array from Ollama for Semantic Search."
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
        # Initialize pgvector and parent-child schema columns
        try:
            self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            self.env.cr.execute("""
                ALTER TABLE topic_chatbot_chunk 
                ADD COLUMN IF NOT EXISTS embedding_vector vector(768);
            """)
            self.env.cr.execute("""
                ALTER TABLE topic_chatbot_chunk 
                ADD COLUMN IF NOT EXISTS parent_id INTEGER;
            """)
            self.env.cr.execute("""
                ALTER TABLE topic_chatbot_chunk 
                ADD COLUMN IF NOT EXISTS chunk_type VARCHAR DEFAULT 'standard';
            """)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_parent_id_idx
                ON topic_chatbot_chunk (parent_id);
            """)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_type_idx
                ON topic_chatbot_chunk (chunk_type);
            """)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_embedding_idx
                ON topic_chatbot_chunk USING hnsw (embedding_vector vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
            # Schema & Migration for Ollama embedding vector:
            # Upgrade to 1024 dimensions (BAAI/bge-m3) with automatic migration
            self.env.cr.execute("""
                DO $$
                DECLARE
                    col_type text;
                BEGIN
                    SELECT format_type(atttypid, atttypmod) INTO col_type
                    FROM pg_attribute
                    WHERE attrelid = 'topic_chatbot_chunk'::regclass
                      AND attname = 'embedding_vector_ollama';

                    IF col_type = 'vector(768)' THEN
                        DROP INDEX IF EXISTS topic_chatbot_chunk_embedding_ollama_idx;
                        ALTER TABLE topic_chatbot_chunk ALTER COLUMN embedding_vector_ollama TYPE vector(1024) USING NULL;
                    ELSIF col_type IS NULL THEN
                        ALTER TABLE topic_chatbot_chunk ADD COLUMN IF NOT EXISTS embedding_vector_ollama vector(1024);
                    END IF;
                END $$;
            """)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS topic_chatbot_chunk_embedding_ollama_idx
                ON topic_chatbot_chunk USING hnsw (embedding_vector_ollama vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """)
        except Exception as e:
            _logger.error("Failed to initialize schema/pgvector on topic_chatbot_chunk: %s", str(e))
            self.env.cr.rollback()
        return res

    @api.model
    def _normalize_embedding_model(self, model_name=None):
        """Clean and normalize model name to the centralized default embedding model."""
        if not model_name:
            params = self.env['ir.config_parameter'].sudo()
            model_name = params.get_param('topic_chatbot.embedding_model', default=DEFAULT_EMBEDDING_MODEL)
        clean = (model_name or DEFAULT_EMBEDDING_MODEL).replace('models/', '').strip()
        # Retired/legacy models mapped directly to the active gemini-embedding-2
        if clean in ('text-embedding-004', 'embedding-001', ''):
            clean = DEFAULT_EMBEDDING_MODEL
        return clean or DEFAULT_EMBEDDING_MODEL

    @api.model
    def _get_embedding_batch_settings(self, batch_size=None):
        """Return conservative, configurable batch settings for Gemini embeddings."""
        params = self.env['ir.config_parameter'].sudo()

        try:
            configured_size = int(params.get_param('topic_chatbot.embedding_batch_size') or 0)
        except Exception:
            configured_size = 0
        try:
            configured_delay = float(params.get_param('topic_chatbot.embedding_batch_delay_seconds') or 0.0)
        except Exception:
            configured_delay = 0.0

        raw_size = batch_size or configured_size or EMBEDDING_BATCH_SIZE
        effective_batch_size = min(max(int(raw_size), 1), 100)
        delay_seconds = max(configured_delay or PROACTIVE_BATCH_DELAY_SECONDS, 0.0)
        return effective_batch_size, delay_seconds

    @api.model
    def _acquire_compute_lock(self, target_label='Compute'):
        """Serialize compute batches (embeddings/OCR) across Odoo workers sharing this DB."""
        self.env.cr.execute(
            "SELECT pg_advisory_lock(%s)",
            (OLLAMA_COMPUTE_LOCK_KEY,),
        )

    @api.model
    def _release_compute_lock(self, target_label='Compute'):
        try:
            self.env.cr.execute(
                "SELECT pg_advisory_unlock(%s)",
                (OLLAMA_COMPUTE_LOCK_KEY,),
            )
        except Exception as e:
            _logger.warning("Failed to release compute lock: %s", str(e))

    def _acquire_gemini_embedding_lock(self, target_model):
        return self._acquire_compute_lock(target_model)

    def _release_gemini_embedding_lock(self, target_model):
        return self._release_compute_lock(target_model)

    @api.model
    def _generate_embedding(self, text, api_key=None, model_name=None, provider=None):
        """Generate text vector embedding for a single text.
        Supports dual modes: 'gemini' and 'ollama' (100% local offline).
        """
        if not text:
            return None

        cfg = embedding_service.get_embedding_config(self.env)
        active_provider = provider or cfg['provider']

        # Chế độ 2: 100% Local Ollama Only (Không gọi Gemini)
        if active_provider == 'ollama':
            return embedding_service.generate_ollama_embedding_single(
                cfg['ollama_url'], cfg['ollama_model'], text
            )

        # Chế độ 1: Gemini API
        effective_api_key = api_key or cfg['gemini_key']
        if not effective_api_key:
            return None

        target_model = self._normalize_embedding_model(model_name)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:embedContent?key={effective_api_key}"
        payload = {
            "model": f"models/{target_model}",
            "content": {
                "parts": [{"text": text}]
            },
            "outputDimensionality": 768
        }
        headers = {'Content-Type': 'application/json'}

        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                res = requests.post(url, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    res_json = res.json()
                    values = res_json.get('embedding', {}).get('values', [])
                    if values:
                        return json.dumps(values)
                    return None
                elif res.status_code == 429:
                    retry_after = res.headers.get('Retry-After')
                    try:
                        sleep_seconds = float(retry_after) if retry_after else BACKOFF_DELAYS[attempt]
                    except Exception:
                        sleep_seconds = BACKOFF_DELAYS[attempt]
                    sleep_seconds = min(max(sleep_seconds, 5.0), 65.0)
                    _logger.warning(
                        "Gemini embedContent 429 (Rate Limit) on '%s' (attempt %d/%d). Sleeping %.1fs for quota window reset...",
                        target_model, attempt + 1, MAX_RETRY_ATTEMPTS, sleep_seconds
                    )
                    time.sleep(sleep_seconds)
                    continue
                else:
                    _logger.warning("Gemini embedContent HTTP %s for model '%s': %s", res.status_code, target_model, res.text[:200])
                    break
            except requests.exceptions.Timeout:
                time.sleep(2.0)
                continue
            except Exception as e:
                err_msg = str(e)
                if effective_api_key:
                    err_msg = err_msg.replace(effective_api_key, "REDACTED")
                _logger.warning("Failed to generate embedding via Gemini API (%s, attempt %d): %s", target_model, attempt + 1, err_msg)
                time.sleep(2.0)

        return None

    @api.model
    def _generate_embeddings_batch(self, texts, api_key=None, model_name=None, batch_size=None, chunk_records=None, provider=None, document_id=None):
        """Generate text vector embeddings for multiple texts.
        Supports dual modes:
        - Mode 1 ('gemini'): Gemini API primary with automatic fallback to Ollama if 429 quota exhausted.
        - Mode 2 ('ollama'): 100% Local Ollama Only, completely independent from Gemini.
        """
        if not texts:
            return []

        cfg = embedding_service.get_embedding_config(self.env)
        active_provider = provider or cfg['provider']

        # Chế độ 2: 100% Local Ollama Only (Hoàn toàn KHÔNG đụng tới Gemini API)
        if active_provider == 'ollama':
            params = self.env['ir.config_parameter'].sudo()
            custom_ollama_batch = params.get_param('topic_chatbot.ollama_batch_size')
            adaptive_batch = int(custom_ollama_batch) if custom_ollama_batch and custom_ollama_batch.isdigit() else None
            _logger.info(
                "Mode: Local Ollama Only. Generating embeddings for %d chunks using %s at %s (Batch: %s, No Gemini calls).",
                len(texts), cfg['ollama_model'], cfg['ollama_url'], adaptive_batch or "Adaptive Benchmark (16->48)"
            )

            def save_ollama_batch(batch_indices, batch_results, progress_info=None):
                if chunk_records:
                    try:
                        with self.env.cr.savepoint():
                            for b_i, emb_json in enumerate(batch_results):
                                if emb_json:
                                    real_idx = batch_indices[b_i]
                                    if real_idx < len(chunk_records):
                                        rec = chunk_records[real_idx]
                                        rec.write({'embedding_ollama': emb_json})
                                        self.env.cr.execute(
                                            "UPDATE topic_chatbot_chunk SET embedding_vector_ollama = %s WHERE id = %s",
                                            (emb_json, rec.id)
                                        )
                        self.env.cr.commit()
                        _logger.info(
                            "    -> [DATABASE] Saved %d vectors into PostgreSQL (Chunk ID %s -> %s)",
                            sum(1 for e in batch_results if e),
                            chunk_records[batch_indices[0]].id,
                            chunk_records[batch_indices[-1]].id
                        )
                    except Exception as persist_err:
                        _logger.warning("Ollama batch save failed: %s", str(persist_err))

                if document_id and progress_info:
                    try:
                        progress_pct = progress_info.get('progress_pct', 0)
                        total_p = progress_info.get('total_processed', 0)
                        total_t = progress_info.get('total_texts', 0)
                        eta_s = progress_info.get('eta_str', '')

                        self.env['bus.bus']._sendone('broadcast', 'topic_chatbot.document/progress', {
                            'document_id': document_id,
                            'processed_chunks': total_p,
                            'total_chunks': total_t,
                            'progress_pct': round(progress_pct, 1),
                            'eta_str': eta_s,
                        })
                        self.env.cr.execute(
                            "UPDATE topic_chatbot_document SET processing_progress = %s WHERE id = %s",
                            (int(progress_pct), document_id)
                        )
                        self.env.cr.commit()
                    except Exception as bus_err:
                        _logger.debug("Failed to broadcast Ollama embedding progress: %s", str(bus_err))

            self._acquire_compute_lock('Ollama Embeddings')
            try:
                results = embedding_service.generate_ollama_embeddings_batch(
                    cfg['ollama_url'], cfg['ollama_model'], texts,
                    batch_size=adaptive_batch,
                    on_batch_success=save_ollama_batch
                )
                return results
            finally:
                self._release_compute_lock('Ollama Embeddings')

        # Chế độ 1: Gemini API
        effective_api_key = api_key or cfg['gemini_key']
        if not effective_api_key:
            _logger.warning("Gemini API Key is not configured for embedding generation.")
            return [None] * len(texts)

        target_model = self._normalize_embedding_model(model_name)
        headers = {'Content-Type': 'application/json'}
        results = [None] * len(texts)
        effective_batch_size, batch_delay_seconds = self._get_embedding_batch_settings(batch_size)
        
        total_chunks = len(texts)
        total_batches = (total_chunks + effective_batch_size - 1) // effective_batch_size
        overall_start_time = time.time()

        _logger.info(
            "Starting embedding generation for %d chunks (model: '%s', batch size: %d, batch delay: %.1fs, total batches: %d)",
            total_chunks, target_model, effective_batch_size, batch_delay_seconds, total_batches
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:batchEmbedContents?key={effective_api_key}"

        rate_limit_exhausted = False

        # Process in batches
        for batch_idx, start_idx in enumerate(range(0, total_chunks, effective_batch_size), start=1):
            if rate_limit_exhausted:
                _logger.warning(
                    "Skipping remaining Gemini embedding batches after sustained 429 rate limit on '%s'.",
                    target_model,
                )
                break

            batch_chunk_texts = texts[start_idx:start_idx + effective_batch_size]
            batch_indices = list(range(start_idx, start_idx + len(batch_chunk_texts)))
            batch_start_time = time.time()

            payload = {
                "requests": [
                    {
                        "model": f"models/{target_model}",
                        "content": {"parts": [{"text": t}]},
                        "outputDimensionality": 768
                    }
                    for t in batch_chunk_texts
                ]
            }

            batch_succeeded = False
            last_status_code = None
            last_was_rate_limit = False

            for attempt in range(MAX_RETRY_ATTEMPTS):
                try:
                    self._acquire_compute_lock('Gemini Batch Call')
                    try:
                        res = requests.post(url, headers=headers, json=payload, timeout=60)
                    finally:
                        self._release_compute_lock('Gemini Batch Call')
                    last_status_code = res.status_code
                    if res.status_code == 200:
                        res_json = res.json()
                        embeddings = res_json.get('embeddings', [])
                        for b_i, emb in enumerate(embeddings):
                            vals = emb.get('values', [])
                            if vals and b_i < len(batch_indices):
                                results[batch_indices[b_i]] = json.dumps(vals)
                        batch_succeeded = True
                        break
                    elif res.status_code == 429:
                        last_was_rate_limit = True
                        retry_after = res.headers.get('Retry-After')
                        try:
                            sleep_seconds = float(retry_after) if retry_after else BACKOFF_DELAYS[attempt]
                        except Exception:
                            sleep_seconds = BACKOFF_DELAYS[attempt]
                        sleep_seconds = min(max(sleep_seconds, 5.0), 65.0)
                        if attempt + 1 >= MAX_RETRY_ATTEMPTS:
                            _logger.warning(
                                "Gemini batchEmbedContents 429 (Rate Limit) on '%s' (batch %d/%d, attempt %d/%d). Retry budget exhausted.",
                                target_model, batch_idx, total_batches, attempt + 1, MAX_RETRY_ATTEMPTS
                            )
                            break
                        _logger.warning(
                            "Gemini batchEmbedContents 429 (Rate Limit) on '%s' (batch %d/%d, attempt %d/%d). Sleeping %.1fs for quota reset...",
                            target_model, batch_idx, total_batches, attempt + 1, MAX_RETRY_ATTEMPTS, sleep_seconds
                        )
                        time.sleep(sleep_seconds)
                        continue
                    elif res.status_code in (404, 400):
                        _logger.info("batchEmbedContents HTTP %s on model '%s', falling back to sequential calls on same model.", res.status_code, target_model)
                        break
                    else:
                        _logger.warning("batchEmbedContents HTTP %s for '%s': %s", res.status_code, target_model, res.text[:200])
                        break
                except requests.exceptions.Timeout:
                    if attempt + 1 < MAX_RETRY_ATTEMPTS:
                        time.sleep(2.0)
                    continue
                except Exception as e:
                    err_msg = str(e)
                    if effective_api_key:
                        err_msg = err_msg.replace(effective_api_key, "REDACTED")
                    _logger.warning("batchEmbedContents error (%s, batch %d/%d): %s", target_model, batch_idx, total_batches, err_msg)
                    if attempt + 1 < MAX_RETRY_ATTEMPTS:
                        time.sleep(2.0)

            # Fallback to sequential calls ONLY on 404/400
            if not batch_succeeded and last_status_code in (404, 400):
                _logger.info(
                    "Fallback to sequential embedding for batch %d/%d (%d chunks) on model '%s'", 
                    batch_idx, total_batches, len(batch_chunk_texts), target_model
                )
                for b_i, text in enumerate(batch_chunk_texts):
                    emb_json = self._generate_embedding(text, effective_api_key, target_model, provider='gemini')
                    results[batch_indices[b_i]] = emb_json
                    time.sleep(max(batch_delay_seconds, 1.0))
                batch_succeeded = any(results[i] for i in batch_indices)

            if not batch_succeeded and last_was_rate_limit:
                rate_limit_exhausted = True

            # Incremental DB persistence per batch if chunk_records provided
            if chunk_records and batch_succeeded:
                try:
                    with self.env.cr.savepoint():
                        for b_i in range(len(batch_chunk_texts)):
                            global_idx = batch_indices[b_i]
                            emb_json = results[global_idx]
                            if emb_json and global_idx < len(chunk_records):
                                rec = chunk_records[global_idx]
                                rec.write({'embedding': emb_json})
                                self.env.cr.execute(
                                    "UPDATE topic_chatbot_chunk SET embedding_vector = %s WHERE id = %s",
                                    (emb_json, rec.id)
                                )
                    self.env.cr.commit()
                except Exception as persist_err:
                    _logger.warning("Incremental save failed for batch %d: %s", batch_idx, str(persist_err))

            if document_id and batch_succeeded:
                try:
                    processed_chunks = min(start_idx + len(batch_chunk_texts), total_chunks)
                    progress_pct = (processed_chunks / total_chunks) * 100.0
                    elapsed_so_far = time.time() - overall_start_time
                    avg_per_chunk = elapsed_so_far / processed_chunks if processed_chunks > 0 else 0
                    remaining_chunks = total_chunks - processed_chunks
                    eta_sec = remaining_chunks * avg_per_chunk
                    if eta_sec >= 3600:
                        eta_str = f"{int(eta_sec // 3600)}h {int((eta_sec % 3600) // 60)}m"
                    elif eta_sec >= 60:
                        eta_str = f"{int(eta_sec // 60)}m {int(eta_sec % 60):02d}s"
                    else:
                        eta_str = f"{int(eta_sec)}s"

                    self.env['bus.bus']._sendone('broadcast', 'topic_chatbot.document/progress', {
                        'document_id': document_id,
                        'processed_chunks': processed_chunks,
                        'total_chunks': total_chunks,
                        'progress_pct': round(progress_pct, 1),
                        'eta_str': eta_str,
                    })
                    self.env.cr.execute(
                        "UPDATE topic_chatbot_document SET processing_progress = %s WHERE id = %s",
                        (int(progress_pct), document_id)
                    )
                    self.env.cr.commit()
                except Exception as bus_err:
                    _logger.debug("Failed to broadcast Gemini embedding progress: %s", str(bus_err))

            batch_duration = time.time() - batch_start_time
            _logger.info(
                "Processed batch %d/%d (%d chunks) in %.2fs [Status: %s]",
                batch_idx, total_batches, len(batch_chunk_texts), batch_duration,
                "OK" if batch_succeeded else "FAILED"
            )

            if not rate_limit_exhausted and start_idx + effective_batch_size < total_chunks:
                time.sleep(batch_delay_seconds)

            # Auto-Fallback to Ollama if Gemini was exhausted by rate limits
            if rate_limit_exhausted and cfg.get('ollama_url'):
                failed_indices = [i for i, r in enumerate(results) if not r]
                if failed_indices:
                    _logger.info("Gemini quota exhausted (429). Auto-falling back to Ollama for %d remaining chunks...", len(failed_indices))
                    failed_texts = [texts[i] for i in failed_indices]
                    self._acquire_compute_lock('Ollama Fallback Embedding')
                    try:
                        ollama_embs = embedding_service.generate_ollama_embeddings_batch(
                            cfg['ollama_url'], cfg['ollama_model'], failed_texts
                        )
                    finally:
                        self._release_compute_lock('Ollama Fallback Embedding')
                    if chunk_records:
                        try:
                            with self.env.cr.savepoint():
                                for f_idx, emb_json in enumerate(ollama_embs):
                                    if emb_json:
                                        real_idx = failed_indices[f_idx]
                                        rec = chunk_records[real_idx]
                                        rec.write({'embedding_ollama': emb_json})
                                        self.env.cr.execute(
                                            "UPDATE topic_chatbot_chunk SET embedding_vector_ollama = %s WHERE id = %s",
                                            (emb_json, rec.id)
                                        )
                                        results[real_idx] = emb_json
                            self.env.cr.commit()
                            _logger.info("Auto-fallback to Ollama successfully embedded and saved %d chunks into embedding_vector_ollama.", sum(1 for e in ollama_embs if e))
                        except Exception as ex_fb:
                            _logger.warning("Auto-fallback to Ollama save failed: %s", str(ex_fb))

        total_duration = time.time() - overall_start_time
        success_count = sum(1 for r in results if r)
        fail_count = total_chunks - success_count

        if fail_count > 0:
            _logger.warning(
                "Embedding generation completed with issues in %.2fs: %d/%d succeeded, %d failed on model '%s'",
                total_duration, success_count, total_chunks, fail_count, target_model
            )
        else:
            _logger.info(
                "Embedding generation completed successfully in %.2fs: %d/%d chunks embedded on model '%s'",
                total_duration, success_count, total_chunks, target_model
            )

        return results
