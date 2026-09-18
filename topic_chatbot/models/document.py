# -*- coding: utf-8 -*-
import base64
import io
import json
import logging
import re
import requests
import time
import zipfile
import xml.etree.ElementTree as ET
from odoo import api, fields, models
from odoo.exceptions import UserError
from ..services import image_filter, image_classifier, ocr_service, vision_service

_logger = logging.getLogger(__name__)

# Try importing pypdf / PyPDF2
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        PdfReader = None

class TopicChatbotDocument(models.Model):
    _name = 'topic_chatbot.document'
    _description = 'Topic Document'
    _order = 'create_date desc'  # Show newest documents first
    
    # Constants
    STALE_PROCESSING_MINUTES = 60
    DOCUMENT_PROCESS_LOCK_KEY = 830917
    OLLAMA_COMPUTE_LOCK_KEY = 830917

    # Excel chunking constants (adjustable for benchmarking)
    EXCEL_PARENT_CHUNK_SIZE = 3500   # Max chars per parent chunk
    EXCEL_CHILD_CHUNK_SIZE = 800     # Max chars per child chunk (upper bound, never cuts mid-record)
    EXCEL_CHILD_BUDGET_MIN = 800     # Soft minimum budget for child chunk
    EXCEL_CHILD_BUDGET_MAX = 1200    # Soft maximum budget for child chunk (single-row overflow allowed)
    EXCEL_HEADER_COMPACT_THRESHOLD = 15  # Tables with more columns use compact header
    EXCEL_MAX_CARDINALITY_DISPLAY = 25  # Max unique values displayed per column in Sheet Summary
    
    # Basic fields with enhanced validation
    name = fields.Char(
        string='Document Name', 
        required=True,
        help="Descriptive name for the document"
    )
    topic_id = fields.Many2one(
        'topic_chatbot.topic', 
        string='Topic', 
        required=True, 
        ondelete='cascade',
        index=True  # Performance improvement
    )
    datas = fields.Binary(
        string='File Content', 
        required=True, 
        attachment=True,
        help="Binary content of the uploaded file"
    )
    filename = fields.Char(
        string='Filename',
        help="Original filename with extension"
    )
    
    # Enhanced content fields
    text_content = fields.Text(
        string='Extracted Text', 
        readonly=True,
        help="Text content extracted from the document"
    )
    content_length = fields.Integer(
        string='Content Length',
        readonly=True,
        help="Number of characters in extracted text"
    )
    word_count = fields.Integer(
        string='Word Count',
        readonly=True,
        help="Approximate number of words in document"
    )
    
    # Enhanced state management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('partial', 'Partial Embeddings'),
        ('error', 'Error')
    ], string='Status', default='draft', required=True, readonly=True, index=True)
    
    # Metadata fields
    doc_type = fields.Selection([
        ('regulation', 'Quy định / Quy chế'),
        ('process', 'Quy trình'),
        ('report', 'Báo cáo'),
        ('form', 'Biểu mẫu'),
        ('manual', 'Hướng dẫn'),
        ('other', 'Khác'),
    ], string='Loại văn bản', default='other', index=True, help="Phân loại tài liệu phục vụ lọc tìm kiếm")
    department = fields.Char(
        string='Phòng ban áp dụng',
        index=True,
        help="Phòng ban hoặc bộ phận áp dụng tài liệu này (e.g., Kế toán, Nhân sự, IT)"
    )
    apply_year = fields.Integer(
        string='Năm áp dụng',
        index=True,
        help="Năm ban hành hoặc áp dụng của văn bản (e.g., 2024, 2025)"
    )
    layout_type = fields.Char(
        string='Layout Type', 
        readonly=True,
        help="Detected document layout (prose, table, mixed, etc.)"
    )
    file_size = fields.Integer(
        string='File Size (KB)',
        readonly=True,
        help="Original file size in kilobytes"
    )
    processing_time = fields.Float(
        string='Processing Time (s)',
        readonly=True,
        help="Time taken to process the document in seconds"
    )
    estimated_seconds = fields.Integer(
        string='Estimated Duration (s)',
        readonly=True,
        help="Estimated total seconds required to extract text and generate embeddings"
    )
    estimated_time_display = fields.Char(
        string='Thời gian dự kiến',
        readonly=True,
        help="Human-readable estimated processing time (e.g. 'Khoảng 45 giây')"
    )
    processing_start_time = fields.Datetime(
        string='Thời điểm bắt đầu xử lý',
        readonly=True,
        help="Timestamp when background processing started"
    )
    estimated_finish_time = fields.Datetime(
        string='Dự kiến hoàn thành lúc',
        readonly=True,
        help="Estimated completion timestamp"
    )
    processing_progress = fields.Integer(
        string='Tiến độ (%)',
        default=0,
        readonly=True,
        help="Current estimated or actual processing progress percentage"
    )
    error_message = fields.Text(
        string='Error Details',
        readonly=True,
        help="Detailed error message if processing failed"
    )
    
    # Statistics
    chunks_count = fields.Integer(
        string='Chunks Created',
        compute='_compute_chunks_count',
        store=True,
        help="Number of text chunks created from this document"
    )

    @api.model
    def _auto_init(self):
        res = super(TopicChatbotDocument, self)._auto_init()
        try:
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_document_text_content_gin
                ON topic_chatbot_document
                USING gin(to_tsvector('simple', COALESCE(text_content, '')));
            """)
        except Exception as e:
            _logger.warning("Could not create GIN index on topic_chatbot_document: %s", str(e))
        return res

    ocr_job_ids = fields.One2many(
        'topic_chatbot.ocr_job',
        'document_id',
        string='OCR Jobs',
        readonly=True,
        help="Danh sách tác vụ trích xuất OCR cho tài liệu này"
    )
    has_ocr_errors = fields.Boolean(
        string='Có lỗi OCR',
        compute='_compute_has_ocr_errors',
        store=True,
        help="Đánh dấu nếu tác vụ OCR của tài liệu hoàn thành một phần hoặc có lỗi"
    )
    ocr_warning = fields.Char(
        string='Cảnh báo OCR',
        compute='_compute_has_ocr_errors',
        store=True,
        help="Thông báo tóm tắt lỗi hình ảnh OCR"
    )

    @api.depends('ocr_job_ids.state', 'ocr_job_ids.error_message')
    def _compute_has_ocr_errors(self):
        for doc in self:
            err_jobs = doc.ocr_job_ids.filtered(lambda j: j.state in ('done_with_errors', 'failed'))
            if err_jobs:
                doc.has_ocr_errors = True
                doc.ocr_warning = err_jobs[0].error_message or "Tài liệu có hình ảnh chưa thể trích xuất hoàn chỉnh."
            else:
                doc.has_ocr_errors = False
                doc.ocr_warning = False

    @api.depends('chunk_ids')
    def _compute_chunks_count(self):
        """Compute number of chunks created from this document."""
        for doc in self:
            doc.chunks_count = len(doc.chunk_ids)
    
    chunk_ids = fields.One2many(
        'topic_chatbot.chunk',
        'document_id',
        string='Text Chunks',
        readonly=True,
        help="Text chunks extracted from this document"
    )

    @api.onchange('datas', 'filename')
    def _onchange_datas_filename(self):
        """Auto-populate name from filename if name is not set."""
        if self.filename and not self.name:
            clean_name = self.filename.rsplit('.', 1)[0] if '.' in self.filename else self.filename
            self.name = clean_name

    @api.constrains('filename', 'datas')
    def _check_file_extension(self):
        """Validate file extension and size."""
        ALLOWED_EXTENSIONS = ('.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt')
        MAX_FILE_SIZE_MB = 50  # 50MB limit
        
        for doc in self:
            if doc.filename and doc.datas:
                filename_lower = doc.filename.lower()
                
                # Check file extension
                if not filename_lower.endswith(ALLOWED_EXTENSIONS):
                    raise UserError(
                        f"Tệp '{doc.filename}' không đúng định dạng. "
                        "Hệ thống chỉ chấp nhận tệp định dạng: " + 
                        ", ".join(ALLOWED_EXTENSIONS) + "!"
                    )
                
                # Check file size
                if doc.datas:
                    import base64
                    file_size_mb = len(base64.b64decode(doc.datas)) / (1024 * 1024)
                    if file_size_mb > MAX_FILE_SIZE_MB:
                        raise UserError(
                            f"Tệp '{doc.filename}' có kích thước {file_size_mb:.1f}MB "
                            f"vượt quá giới hạn {MAX_FILE_SIZE_MB}MB cho phép!"
                        )

    @api.model_create_multi
    def create(self, vals_list):
        """Enhanced create with metadata calculation."""
        import base64
        
        for vals in vals_list:
            if not vals.get('name') and vals.get('filename'):
                clean_name = vals['filename'].rsplit('.', 1)[0] if '.' in vals['filename'] else vals['filename']
                vals['name'] = clean_name
            if 'datas' in vals or 'filename' in vals:
                vals['state'] = 'draft'
                
                # Calculate file size
                if vals.get('datas'):
                    try:
                        file_content = base64.b64decode(vals['datas'])
                        vals['file_size'] = len(file_content) // 1024  # KB
                    except Exception:
                        pass
                        
        records = super().create(vals_list)
        return records

    def write(self, vals):
        """Enhanced write with state management."""
        import base64
        
        if 'datas' in vals or 'filename' in vals:
            vals['state'] = 'draft'
            
            # Recalculate file size if file changed
            if vals.get('datas'):
                try:
                    file_content = base64.b64decode(vals['datas'])
                    vals['file_size'] = len(file_content) // 1024  # KB
                except Exception:
                    pass
                    
        return super().write(vals)

    def _calculate_estimated_processing_time(self):
        """Calculate estimated processing time in seconds and human-readable string based on file characteristics."""
        import base64
        import datetime
        from ..services import embedding_service

        cfg = embedding_service.get_embedding_config(self.env)
        active_provider = cfg.get('provider') or 'gemini'
        # Heuristic: Ollama bge-m3 takes ~1.2s - 1.5s per chunk on CPU/integrated GPU.
        # Gemini takes ~0.2s per chunk (batch of 20 chunks in ~3s-4s).
        sec_per_chunk = 1.5 if active_provider == 'ollama' else 0.2

        for doc in self:
            est_sec = 20  # Baseline minimum
            filename = (doc.filename or '').lower()
            file_bytes = 0
            if doc.datas:
                try:
                    file_bytes = len(base64.b64decode(doc.datas))
                except Exception:
                    file_bytes = (doc.file_size or 0) * 1024

            if filename.endswith('.docx'):
                # Parsing DOCX is fast; estimate ~15s base + 5s per MB + embedding time
                # Roughly 1 chunk per 4KB text
                est_chunks = max(3, file_bytes // 4000)
                est_sec = 15 + int((file_bytes / (1024 * 1024)) * 5) + int(est_chunks * sec_per_chunk)
            elif filename.endswith(('.xlsx', '.xls')):
                # Excel parsing can be ~10s per 1,000 rows
                # Heuristic: roughly 50KB per 1,000 rows in xlsx
                est_rows = max(100, int((file_bytes / 50000) * 1000))
                parse_time = max(5, int((est_rows / 1000) * 8))
                # Excel child chunks are ~800-1200 chars (~10-15 rows)
                est_chunks = max(5, est_rows // 12)
                est_sec = 10 + parse_time + int(est_chunks * sec_per_chunk)
            elif filename.endswith('.pdf'):
                # Check page count and scan status
                total_pages = 1
                is_scanned = False
                if doc.datas and PdfReader:
                    try:
                        reader = PdfReader(io.BytesIO(base64.b64decode(doc.datas)))
                        total_pages = max(1, len(reader.pages))
                        sample_page = reader.pages[0].extract_text() or ""
                        if len(sample_page.strip()) < 40:
                            is_scanned = True
                    except Exception:
                        pass
                
                if is_scanned:
                    # OCR takes ~15-20s per page
                    est_sec = 10 + (total_pages * 18)
                else:
                    # Text PDF takes ~1s per 3 pages + embedding time
                    parse_time = max(5, total_pages // 2)
                    est_chunks = max(3, total_pages * 2)
                    est_sec = 10 + parse_time + int(est_chunks * sec_per_chunk)
            else:
                # Plain text or CSV
                est_chunks = max(3, file_bytes // 3000)
                est_sec = 10 + max(5, file_bytes // 100000) + int(est_chunks * sec_per_chunk)

            # Cap bounds (realistic upper ceiling of 4 hours instead of 10 minutes)
            est_sec = max(15, min(est_sec, 14400))

            # Format human display
            if est_sec < 60:
                display = f"Khoảng {est_sec} giây"
            elif est_sec < 3600:
                mins = est_sec // 60
                secs = est_sec % 60
                if secs > 0:
                    display = f"Khoảng {mins} phút {secs} giây"
                else:
                    display = f"Khoảng {mins} phút"
            else:
                hours = est_sec // 3600
                mins = (est_sec % 3600) // 60
                if mins > 0:
                    display = f"Khoảng {hours} giờ {mins} phút"
                else:
                    display = f"Khoảng {hours} giờ"

            now = fields.Datetime.now()
            finish_time = fields.Datetime.add(now, seconds=est_sec)

            doc.write({
                'estimated_seconds': est_sec,
                'estimated_time_display': display,
                'processing_start_time': now,
                'estimated_finish_time': finish_time,
                'processing_progress': 5,
            })

    def action_process_document(self):
        """Action method to trigger background processing on selected document(s)."""
        import threading
        stale_cutoff = fields.Datetime.subtract(
            fields.Datetime.now(),
            minutes=self.STALE_PROCESSING_MINUTES,
        )
        draft_docs = self.filtered(
            lambda d: d.state in ('draft', 'error') or (
                d.state == 'processing' and d.write_date and d.write_date <= stale_cutoff
            )
        )
        if not draft_docs:
            return True

        draft_docs.filtered(lambda d: d.state == 'error').write({'state': 'draft'})
        
        # Calculate estimated processing times before launching background thread
        draft_docs._calculate_estimated_processing_time()

        draft_docs.write({
            'state': 'processing',
            'error_message': False,
        })
        self.env.cr.commit()

        db_name = self.env.cr.dbname
        uid = self.env.uid
        doc_ids = draft_docs.ids

        thread = threading.Thread(
            target=self._run_process_documents_in_thread,
            args=(db_name, uid, doc_ids),
            daemon=True
        )
        thread.start()

        if len(draft_docs) == 1:
            doc = draft_docs[0]
            est_text = doc.estimated_time_display or "vài giây"
            notif_msg = f"Đã bắt đầu xử lý tài liệu '{doc.name}'. Dự kiến hoàn thành trong {est_text}. Hệ thống sẽ thông báo khi hoàn thành để bạn bắt đầu đặt câu hỏi."
        else:
            total_est = sum(d.estimated_seconds or 30 for d in draft_docs)
            if total_est < 60:
                time_str = f"{total_est} giây"
            elif total_est < 3600:
                mins = total_est // 60
                secs = total_est % 60
                time_str = f"{mins} phút {secs} giây" if secs > 0 else f"{mins} phút"
            else:
                hours = total_est // 3600
                mins = (total_est % 3600) // 60
                time_str = f"{hours} giờ {mins} phút" if mins > 0 else f"{hours} giờ"
            notif_msg = f"Đã bắt đầu xử lý {len(draft_docs)} tài liệu trong nền (dự kiến tổng: {time_str}). Trạng thái sẽ cập nhật tự động khi hoàn thành."

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Xử lý tài liệu',
                'message': notif_msg,
                'type': 'info',
                'sticky': False,
            }
        }

    @classmethod
    def _run_process_documents_in_thread(cls, db_name, uid, doc_ids):
        """Worker function for running document processing in a separate DB cursor thread."""
        import odoo
        with odoo.registry(db_name).cursor() as new_cr:
            env = api.Environment(new_cr, uid, {})
            documents = env['topic_chatbot.document'].browse(doc_ids)
            for doc in documents:
                try:
                    doc._process_document()
                    new_cr.commit()
                except Exception as e:
                    _logger.error("Background document processing error for doc id %s: %s", doc.id, str(e))
                    new_cr.rollback()
                    try:
                        env['topic_chatbot.document'].browse(doc.id).sudo().write({
                            'state': 'error',
                            'text_content': "Lỗi xử lý nền: %s" % str(e),
                        })
                        new_cr.commit()
                    except Exception as write_err:
                        new_cr.rollback()
                        _logger.error(
                            "Failed to mark document %s as error after background failure: %s",
                            doc.id,
                            str(write_err),
                        )

    @api.model
    def _cron_process_documents(self):
        """Cron job to process draft documents and recover stale processing records using SKIP LOCKED."""
        with self.env.registry.cursor() as dedicated_cr:
            query = """
                SELECT id, state FROM topic_chatbot_document
                WHERE (state = 'draft')
                   OR (state = 'processing' AND write_date <= (now() at time zone 'UTC') - interval '%s minutes')
                ORDER BY id ASC
                LIMIT 5
                FOR UPDATE SKIP LOCKED
            """
            dedicated_cr.execute(query, (self.STALE_PROCESSING_MINUTES,))
            rows = dedicated_cr.fetchall()
            if not rows:
                return

            doc_ids_to_process = [r[0] for r in rows]
            # Mark processing immediately and commit to release row-level locks
            dedicated_cr.execute(
                "UPDATE topic_chatbot_document SET state = 'processing', write_date = (now() at time zone 'UTC') WHERE id IN %s",
                (tuple(doc_ids_to_process),)
            )
            dedicated_cr.commit()

        # Process each document
        for doc_id in doc_ids_to_process:
            doc = self.browse(doc_id)
            if not doc.exists():
                continue
            _logger.info("Cron processing document %s (id=%s)", doc.name, doc.id)
            try:
                doc._process_document()
            except Exception as e:
                _logger.error("Error processing document %s in cron: %s", doc.id, str(e))

    def _process_document(self):
        """Enhanced document processing with better error handling and statistics."""
        import time
        import base64
        
        for doc in self:
            start_time = time.time()
            
            # Advisory lock to prevent concurrent processing
            doc.env.cr.execute(
                "SELECT pg_try_advisory_lock(%s, %s)",
                (self.DOCUMENT_PROCESS_LOCK_KEY, doc.id),
            )
            lock_acquired = doc.env.cr.fetchone()[0]
            if not lock_acquired:
                _logger.info(
                    "Skipping document %s (id=%s) because another worker is already processing it.",
                    doc.name, doc.id,
                )
                continue

            # Early return for empty documents
            if not doc.datas:
                doc.write({
                    'state': 'done',
                    'processing_time': time.time() - start_time,
                    'content_length': 0,
                    'word_count': 0
                })
                doc.env.cr.execute(
                    "SELECT pg_advisory_unlock(%s, %s)",
                    (self.DOCUMENT_PROCESS_LOCK_KEY, doc.id),
                )
                doc.env.cr.fetchone()
                continue

            try:
                doc.write({'state': 'processing'})
                doc.env.cr.commit()
                
                # Decode base64 file content
                file_content = base64.b64decode(doc.datas)
                filename = (doc.filename or '').lower()
                extracted_text = ""

                # Extract text based on file type
                excel_structure = None
                if filename.endswith('.pdf'):
                    extracted_text = doc._extract_pdf_text(file_content)
                elif filename.endswith('.docx'):
                    extracted_text = doc._extract_docx_text(file_content)
                elif filename.endswith(('.xlsx', '.xls')):
                    excel_structure = doc._extract_excel_structure(file_content)
                    extracted_text = doc._render_excel_structure_to_text(excel_structure)
                elif filename.endswith(('.txt', '.csv')):
                    extracted_text = doc._extract_txt_or_csv_text(file_content)
                else:
                    raise UserError(
                        f"Tệp '{doc.filename}' không được hỗ trợ. "
                        "Hệ thống chỉ chấp nhận tệp định dạng .pdf, .docx, .xlsx, .xls, .csv hoặc .txt!"
                    )

                # Handle embedded images OCR if enabled
                params = doc.env['ir.config_parameter'].sudo()
                enable_ocr = params.get_param('topic_chatbot.enable_image_ocr', 'False').lower() in ('true', '1')
                ocr_mode = params.get_param('topic_chatbot.ocr_processing_mode', 'queue')
                ocr_job = None

                if enable_ocr and (filename.endswith('.pdf') or filename.endswith('.docx')):
                    images_extracted = []
                    if filename.endswith('.pdf'):
                        images_extracted = doc._extract_pdf_images(file_content)
                    elif filename.endswith('.docx'):
                        images_extracted = doc._extract_docx_images(file_content)

                    if images_extracted:
                        _logger.info("Found %d valid embedded images in document %s (id=%s)", len(images_extracted), doc.name, doc.id)
                        
                        # Enforce max_images limit to avoid system overload
                        try:
                            max_imgs = int(params.get_param('topic_chatbot.ocr_max_images') or 15)
                        except (ValueError, TypeError):
                            max_imgs = 15
                        if len(images_extracted) > max_imgs:
                            _logger.info("Capping extracted images for doc %s from %d to %d (ocr_max_images)", doc.id, len(images_extracted), max_imgs)
                            images_extracted = images_extracted[:max_imgs]

                        # Create OCR job in pending state for async background execution
                        ocr_job = doc.env['topic_chatbot.ocr_job'].create({
                            'document_id': doc.id,
                            'images_count': len(images_extracted),
                            'state': 'pending'
                        })

                        # Create lines and check MD5 cache
                        cache_model = doc.env['topic_chatbot.ocr_cache']
                        for img_idx, img_bytes, img_hash in images_extracted:
                            cached_text = cache_model.lookup_cache(img_hash)
                            if cached_text:
                                doc.env['topic_chatbot.ocr_job_image_line'].create({
                                    'job_id': ocr_job.id,
                                    'image_index': img_idx,
                                    'image_hash': img_hash,
                                    'state': 'done',
                                    'extracted_text': cached_text,
                                    'category': 'text_table',
                                    'processing_time': 0.01,
                                })
                            else:
                                doc.env['topic_chatbot.ocr_job_image_line'].create({
                                    'job_id': ocr_job.id,
                                    'image_index': img_idx,
                                    'image_hash': img_hash,
                                    'state': 'pending',
                                })

                # Calculate text statistics
                content_length = len(extracted_text) if extracted_text else 0
                word_count = len(extracted_text.split()) if extracted_text else 0

                # Update document with extracted content
                doc.write({
                    'text_content': extracted_text,
                    'content_length': content_length,
                    'word_count': word_count
                })
                
                # Security check for prompt injection
                doc._warn_prompt_injection_patterns(extracted_text)

                # Remove old chunks and create new ones
                doc.env['topic_chatbot.chunk'].search([('document_id', '=', doc.id)]).unlink()

                # Create new chunks with Vector Embeddings
                chunks_created = 0
                chunks_with_embeddings = 0
                emb_warning = False

                if extracted_text and len(extracted_text.strip()) > 10:
                    from ..services import embedding_service
                    cfg = embedding_service.get_embedding_config(doc.env)
                    active_provider = cfg.get('provider') or 'gemini'
                    api_key = cfg.get('gemini_key') or ''
                    embedding_model = cfg.get('gemini_model') or 'gemini-embedding-2'
                    is_provider_ready = (active_provider == 'ollama' and bool(cfg.get('ollama_url'))) or (active_provider == 'gemini' and bool(api_key))

                    if excel_structure:
                        groups = doc._chunk_excel_structure(excel_structure)
                    else:
                        groups = doc._chunk_text(extracted_text)

                    # Create Parent chunks and prepare Child records
                    parent_vals = []
                    for p_seq, group in enumerate(groups, start=1):
                        parent_vals.append({
                            'topic_id': doc.topic_id.id,
                            'document_id': doc.id,
                            'sequence': p_seq,
                            'content': group['parent'],
                            'chunk_type': 'parent',
                            'embedding': False,
                        })

                    parent_recs = doc.env['topic_chatbot.chunk'].create(parent_vals)
                    
                    # Prepare child chunks referencing their parent
                    child_vals = []
                    child_seq = 1
                    for parent_rec, group in zip(parent_recs, groups):
                        for child_text in group['children']:
                            child_vals.append({
                                'topic_id': doc.topic_id.id,
                                'document_id': doc.id,
                                'parent_id': parent_rec.id,
                                'sequence': child_seq,
                                'content': child_text,
                                'chunk_type': 'child',
                            })
                            child_seq += 1

                    created_children = doc.env['topic_chatbot.chunk'].create(child_vals)
                    chunks_created = len(created_children)

                    # Batch generate embeddings ONLY for child chunks
                    valid_children = [c for c in created_children if is_provider_ready and len(c.content.strip()) > 10]
                    valid_texts = [c.content for c in valid_children]

                    embeddings_list = []
                    if valid_texts:
                        try:
                            embeddings_list = doc.env['topic_chatbot.chunk']._generate_embeddings_batch(
                                valid_texts, api_key, embedding_model, chunk_records=valid_children, provider=active_provider, document_id=doc.id
                            )
                        except Exception as emb_err:
                            _logger.warning("Error during batch embedding generation for document %s: %s", doc.name, str(emb_err))
                            embeddings_list = [None] * len(valid_texts)

                    chunks_with_embeddings = sum(1 for e in embeddings_list if e)

                    if len(valid_texts) > 0 and chunks_with_embeddings == 0:
                        emb_warning = "Tài liệu đã trích xuất thành công nhưng không tạo được Vector Embeddings (do chạm hạn mức API 429 hoặc lỗi kết nối). Bạn có thể bấm 'Bù Embedding' hoặc 'Xử lý lại' sau vài phút."
                        _logger.warning("Document '%s' (id=%s): All %d child chunk embeddings failed.", doc.name, doc.id, len(valid_texts))
                    elif chunks_with_embeddings < len(valid_texts):
                        emb_warning = f"Đã tạo Vector Embeddings cho {chunks_with_embeddings}/{len(valid_texts)} đoạn (một số đoạn bị lỗi rate limit). Bạn có thể bấm 'Bù Embedding' để bổ sung."
                        _logger.warning("Document '%s' (id=%s): %d/%d child chunk embeddings succeeded.", doc.name, doc.id, chunks_with_embeddings, len(valid_texts))
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Determine final state based on embedding completeness
                if chunks_created > 0 and chunks_with_embeddings < chunks_created:
                    final_state = 'partial'
                else:
                    final_state = 'done'

                # Final state update
                doc.write({
                    'state': final_state,
                    'processing_time': processing_time,
                    'processing_progress': 100,
                    'error_message': emb_warning if emb_warning else False
                })

                # Broadcast bus notification so frontend countdown widgets & forms update in realtime
                try:
                    doc.env['bus.bus']._sendone('broadcast', 'topic_chatbot.document/status_changed', {
                        'document_id': doc.id,
                        'state': final_state,
                        'name': doc.name,
                        'processing_time': round(processing_time, 1),
                        'error_message': emb_warning if emb_warning else False,
                    })
                except Exception as bus_err:
                    _logger.debug("Could not send bus notification: %s", str(bus_err))
                
                _logger.info(
                    "Document '%s' (id=%s) processing finished in %.2fs [State: %s]: "
                    "Text: %d chars, %d words | Chunks: %d created, %d/%d embedded (%.1f%%)",
                    doc.name, doc.id, processing_time, final_state,
                    content_length, word_count, chunks_created, chunks_with_embeddings, chunks_created,
                    (chunks_with_embeddings / chunks_created * 100.0) if chunks_created else 100.0
                )

                # Stage 2: Trigger async background OCR processing immediately if document has embedded images
                if ocr_job:
                    doc.env.cr.commit()
                    doc.env['topic_chatbot.ocr_job']._trigger_async_ocr_job(ocr_job.id)

                if excel_structure:
                    sheet_count = len(excel_structure)
                    raw_rows = sum(len(s.get('rows', [])) for s in excel_structure)
                    avg_child_len = (sum(len(c.content or '') for c in created_children) / len(created_children)) if 'created_children' in locals() and created_children else 0
                    eff_b_size, _ = doc.env['topic_chatbot.chunk']._get_embedding_batch_settings()
                    batch_count = (len(valid_texts) + eff_b_size - 1) // eff_b_size if 'valid_texts' in locals() and valid_texts else 0
                    _logger.info(
                        "[EXCEL_PIPELINE]\n"
                        "  - document_id: %s\n"
                        "  - document_name: '%s'\n"
                        "  - sheet_count: %d\n"
                        "  - raw_rows: %d\n"
                        "  - parent_count: %d\n"
                        "  - child_count: %d\n"
                        "  - embedded_child_count: %d\n"
                        "  - batch_count: %d\n"
                        "  - avg_child_size_chars: %.1f\n"
                        "  - text_content_length: %d\n"
                        "  - duration_seconds: %.2f\n"
                        "  - final_state: '%s'",
                        doc.id, doc.name, sheet_count, raw_rows,
                        len(parent_recs) if 'parent_recs' in locals() and parent_recs else 0,
                        chunks_created, chunks_with_embeddings, batch_count,
                        avg_child_len, content_length, processing_time, final_state
                    )
                
            except Exception as e:
                processing_time = time.time() - start_time
                err_msg = str(e)
                
                _logger.error(
                    "Error processing document %s (id=%s) after %.2fs: %s", 
                    doc.name, doc.id, processing_time, err_msg
                )
                
                doc.write({
                    'state': 'error',
                    'processing_time': processing_time,
                    'processing_progress': 0,
                    'error_message': err_msg,
                    'text_content': f"LỖI XỬ LÝ: {err_msg}",
                    'content_length': 0,
                    'word_count': 0
                })

                try:
                    doc.env['bus.bus']._sendone('broadcast', 'topic_chatbot.document/status_changed', {
                        'document_id': doc.id,
                        'state': 'error',
                        'name': doc.name,
                        'processing_time': round(processing_time, 1),
                        'error_message': err_msg,
                    })
                except Exception as bus_err:
                    _logger.debug("Could not send bus error notification: %s", str(bus_err))
            finally:
                try:
                    doc.env.cr.execute(
                        "SELECT pg_advisory_unlock(%s, %s)",
                        (self.DOCUMENT_PROCESS_LOCK_KEY, doc.id),
                    )
                except Exception as unlock_err:
                    _logger.warning(
                        "Failed to release processing lock for document %s (id=%s): %s",
                        doc.name, doc.id, str(unlock_err),
                    )

    def _clean_extracted_text(self, text):
        """Clean and normalize extracted text from PDF engines.
        
        Removes excessive whitespace, fixes common OCR errors,
        and improves text readability.
        """
        if not text:
            return ""
        
        import re
        
        # Remove excessive whitespace and normalize line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple empty lines → double line break
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs → single space
        text = re.sub(r'\n[ \t]+', '\n', text)  # Leading whitespace after newlines
        text = re.sub(r'[ \t]+\n', '\n', text)  # Trailing whitespace before newlines
        
        # Fix common PDF extraction issues
        text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)  # Fix hyphenated words split across lines
        text = re.sub(r'([.!?])\s*\n\s*([A-ZÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶ])', r'\1\n\n\2', text)  # Sentence breaks
        
        # Clean up common OCR artifacts
        text = re.sub(r'[^\w\s\n\r.,;:!?()\[\]{}"\'+=\-*/<>@#$%^&|\\`~àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]', '', text)
        
        # Remove lines that are likely headers/footers (very short, just numbers, etc.)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line and not (
                len(line) <= 3 and line.isdigit() or  # Page numbers
                len(line) <= 10 and re.match(r'^[^a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]*$', line)  # Symbol-only lines
            ):
                cleaned_lines.append(line)
        
        result = '\n'.join(cleaned_lines).strip()
        return result if len(result) > 10 else ""  # Ensure meaningful content

    @staticmethod
    def _is_meaningful_pdf_text(text_parts, total_pages=1):
        """Check if extracted PDF text layer is meaningful or just sparse garbage/watermarks.
        
        Enhanced detection considers:
        - Character density per page
        - Presence of actual words vs symbols
        - Text diversity and structure
        """
        if not text_parts:
            return False
            
        full_text = "\n".join(text_parts).strip()
        
        # Basic length check (enhanced thresholds)
        min_chars_overall = 100  # Increased from 50
        min_chars_per_page = 50   # Increased from 35
        
        if len(full_text) < max(min_chars_overall, total_pages * min_chars_per_page):
            return False
        
        # Advanced meaningfulness checks
        import re
        
        # Count actual words (not just symbols/numbers)
        words = re.findall(r'\b[a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]{3,}\b', full_text)
        
        # Require at least 5 actual words per page on average
        if len(words) < max(10, total_pages * 5):
            return False
        
        # Check text diversity (not just repeated headers/footers)
        unique_words = set(word.lower() for word in words)
        if len(unique_words) < max(5, len(words) * 0.3):  # At least 30% word diversity
            return False
        
        # Check for common watermark/header patterns that shouldn't be considered meaningful
        watermark_patterns = [
            r'confidential',
            r'draft',
            r'page\s+\d+',
            r'copyright',
            r'proprietary',
            r'^[^a-zA-Z]*$',  # Lines with no letters
        ]
        
        meaningful_lines = []
        for line in full_text.split('\n'):
            line = line.strip()
            if len(line) > 10:  # Ignore very short lines
                is_watermark = any(re.search(pattern, line, re.IGNORECASE) for pattern in watermark_patterns)
                if not is_watermark:
                    meaningful_lines.append(line)
        
        # Require at least some meaningful lines
        return len(meaningful_lines) >= max(2, total_pages)

    def _extract_pdf_text(self, file_content):
        """Extract text from PDF using multiple engines with intelligent fallback.
        
        Strategy:
        1. Try native text extraction (fitz → pypdf → PyPDF2)
        2. Check if extracted text is meaningful
        3. Fall back to Gemini Vision OCR for scanned PDFs
        """
        text_parts = []
        total_pages = 1

        # Engine 1: PyMuPDF (fitz) - Best & fastest PDF text extractor
        try:
            import fitz
            doc_fitz = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc_fitz)
            
            # Enhanced text extraction with better formatting
            for page_num, page in enumerate(doc_fitz, 1):
                # Try different text extraction methods
                text_methods = [
                    lambda p: p.get_text(),  # Default method
                    lambda p: p.get_text("text"),  # Plain text
                    lambda p: p.get_text("blocks"),  # Block-based (better structure)
                ]
                
                page_text = ""
                for method in text_methods:
                    try:
                        result = method(page)
                        if isinstance(result, str):
                            page_text = result
                        elif isinstance(result, list):  # blocks method returns list
                            page_text = "\n".join([block[4] for block in result if len(block) > 4 and block[4].strip()])
                        
                        if page_text and page_text.strip():
                            break
                    except Exception:
                        continue
                
                if page_text and page_text.strip():
                    # Clean up the extracted text
                    cleaned_text = self._clean_extracted_text(page_text.strip())
                    if cleaned_text:
                        text_parts.append(f"--- Trang {page_num} ---\n{cleaned_text}")
            
            doc_fitz.close()
            
            if text_parts and self._is_meaningful_pdf_text(text_parts, total_pages):
                return "\n".join(text_parts)
                
        except ImportError:
            _logger.info("PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
        except Exception as e:
            _logger.debug("PyMuPDF fitz extraction failed: %s", str(e))

        # Engine 2: pypdf (Modern PyPDF) - Enhanced extraction
        if not text_parts or not self._is_meaningful_pdf_text(text_parts, total_pages):
            text_parts = []
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(file_content))
                total_pages = len(reader.pages)
                
                for page_num, page in enumerate(reader.pages, 1):
                    # Try multiple extraction strategies
                    page_text = ""
                    try:
                        # Method 1: Standard extraction
                        page_text = page.extract_text()
                        
                        # Method 2: Enhanced extraction with layout preservation
                        if not page_text or len(page_text.strip()) < 50:
                            page_text = page.extract_text(extraction_mode="layout")
                            
                    except Exception:
                        try:
                            page_text = page.extract_text()
                        except Exception:
                            continue
                    
                    if page_text and page_text.strip():
                        cleaned_text = self._clean_extracted_text(page_text.strip())
                        if cleaned_text:
                            text_parts.append(f"--- Trang {page_num} ---\n{cleaned_text}")
                
                if text_parts and self._is_meaningful_pdf_text(text_parts, total_pages):
                    return "\n".join(text_parts)
                    
            except ImportError:
                _logger.info("pypdf not installed. Install with: pip install pypdf")
            except Exception as e:
                _logger.debug("pypdf extraction failed: %s", str(e))

        # Engine 3: PyPDF2 (Enhanced legacy support)
        if not text_parts or not self._is_meaningful_pdf_text(text_parts, total_pages):
            text_parts = []
            try:
                import PyPDF2
                pdf_stream = io.BytesIO(file_content)
                
                # Handle both old and new PyPDF2 versions
                if hasattr(PyPDF2, 'PdfReader'):
                    reader = PyPDF2.PdfReader(pdf_stream)
                    total_pages = len(reader.pages)
                    
                    for page_num, page in enumerate(reader.pages, 1):
                        # Try different extraction methods
                        page_text = ""
                        for extract_method in ['extract_text', 'extractText']:
                            if hasattr(page, extract_method):
                                try:
                                    page_text = getattr(page, extract_method)()
                                    if page_text and page_text.strip():
                                        break
                                except Exception:
                                    continue
                        
                        if page_text and page_text.strip():
                            cleaned_text = self._clean_extracted_text(page_text.strip())
                            if cleaned_text:
                                text_parts.append(f"--- Trang {page_num} ---\n{cleaned_text}")
                
                elif hasattr(PyPDF2, 'PdfFileReader'):
                    # Legacy PyPDF2 version
                    reader = PyPDF2.PdfFileReader(pdf_stream)
                    
                    # Handle encrypted PDFs
                    if reader.isEncrypted:
                        try:
                            reader.decrypt('')  # Try empty password
                        except Exception:
                            _logger.warning("PDF is encrypted and cannot be decrypted")
                            pass
                    
                    total_pages = reader.getNumPages()
                    for i in range(total_pages):
                        try:
                            page = reader.getPage(i)
                            page_text = ""
                            
                            # Try different extraction methods
                            for extract_method in ['extract_text', 'extractText']:
                                if hasattr(page, extract_method):
                                    try:
                                        page_text = getattr(page, extract_method)()
                                        if page_text and page_text.strip():
                                            break
                                    except Exception:
                                        continue
                            
                            if page_text and page_text.strip():
                                cleaned_text = self._clean_extracted_text(page_text.strip())
                                if cleaned_text:
                                    text_parts.append(f"--- Trang {i + 1} ---\n{cleaned_text}")
                        except Exception as e:
                            _logger.debug("Error extracting page %d: %s", i + 1, str(e))
                            continue
                
                if text_parts and self._is_meaningful_pdf_text(text_parts, total_pages):
                    return "\n".join(text_parts)
                    
            except ImportError:
                _logger.info("PyPDF2 not installed. Install with: pip install PyPDF2")
            except Exception as e:
                _logger.debug("PyPDF2 extraction failed: %s", str(e))

        # Engine 4: Fallback to Gemini Vision API OCR for scanned image PDFs or PDFs with insufficient text layer
        safe_filename = (self.filename or '').encode('ascii', 'replace').decode('ascii')
        _logger.info(
            "PDF %s text layer is missing or sparse (pages=%s, extracted_parts=%s). Attempting Gemini Vision OCR...", 
            safe_filename, total_pages, len(text_parts)
        )
        
        # Check if Gemini API key is available before attempting OCR
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('topic_chatbot.gemini_api_key')
        if not api_key:
            # If no API key but we have some sparse text, return it
            if text_parts:
                _logger.warning(
                    "Gemini API key not configured, but some text was extracted from %s. "
                    "Configure Gemini API key for better OCR of scanned PDFs.", safe_filename
                )
                return "\n".join(text_parts)
            else:
                raise UserError(
                    f"Tệp PDF '{self.filename}' không chứa lớp văn bản (Text layer) hoặc là tệp PDF dạng hình ảnh/scan. "
                    "Vui lòng cấu hình Gemini API Key trong Cài đặt → Tham số hệ thống để tự động OCR tệp PDF scan, "
                    "hoặc tải lên tệp định dạng .docx / .xlsx / .txt!"
                )
        
        try:
            ocr_text = self._extract_pdf_ocr_gemini(file_content)
            if ocr_text and len(ocr_text.strip()) > 100:  # Ensure meaningful OCR result
                return ocr_text
        except Exception as e:
            _logger.error("Gemini OCR failed for %s: %s", safe_filename, str(e))

        # If Gemini OCR failed but we had some sparse text, return it as last resort
        if text_parts:
            _logger.warning(
                "Gemini OCR failed for %s, falling back to sparse text layer extraction", 
                safe_filename
            )
            return "\n".join(text_parts)

        # If no text extracted at all
        raise UserError(
            f"Không thể trích xuất văn bản từ tệp PDF '{self.filename}'. "
            "Vui lòng kiểm tra:\n"
            "1. Tệp PDF không bị hỏng\n"
            "2. Tệp PDF không bị mã hóa (password protected)\n"
            "3. Gemini API Key đã được cấu hình đúng\n"
            "4. Hoặc chuyển đổi sang định dạng .docx / .xlsx / .txt"
        )

    # ── Gemini Vision API Helpers ─────────────────────────────────────────

    def _gemini_call_vision(self, img_b64, prompt_text, api_key, response_json=False):
        """Call Gemini Vision API with automatic model fallback and improved error handling.

        Args:
            img_b64: Base64-encoded JPEG image string.
            prompt_text: The text prompt to send alongside the image.
            api_key: Gemini API key.
            response_json: If True, request JSON output and parse the response.

        Returns:
            Parsed JSON (dict or list) when *response_json* is True,
            otherwise a raw text string. Returns ``{}`` / ``""`` on failure.
        """
        import json as json_lib
        import requests
        import time

        # Updated model list with latest Gemini models
        models_to_try = [
            'gemini-2.0-flash-exp',     # Latest experimental model
            'gemini-1.5-flash',         # Fast and reliable  
            'gemini-1.5-pro',          # High quality
            'gemini-pro-vision'         # Fallback
        ]

        for model_idx, model_name in enumerate(models_to_try):
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model_name}:generateContent?key={api_key}"
            )
            
            gen_config = {
                "temperature": 0.1,  # Low temperature for consistent OCR
                "maxOutputTokens": 8192,  # Sufficient for large tables
            }
            
            if response_json:
                gen_config["responseMimeType"] = "application/json"

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                    ]
                }],
                "generationConfig": gen_config,
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE"
                    }
                ]
            }

            # Adaptive retry strategy
            max_retries = 3 if model_idx == 0 else 2  # More retries for primary model
            
            for attempt in range(max_retries):
                try:
                    # Timeout increases with each retry
                    timeout = 30 + (attempt * 15)  # 30s, 45s, 60s
                    
                    res = requests.post(url, json=payload, timeout=timeout)
                    
                    if res.status_code == 200:
                        res_json = res.json()
                        candidates = res_json.get('candidates', [])
                        
                        if candidates and len(candidates) > 0:
                            content = candidates[0].get('content', {})
                            parts = content.get('parts', [])
                            
                            if parts and len(parts) > 0:
                                raw_text = parts[0].get('text', '')
                                if raw_text:
                                    if response_json:
                                        try:
                                            return json_lib.loads(raw_text)
                                        except json_lib.JSONDecodeError as e:
                                            _logger.warning(
                                                "Failed to parse JSON response from %s: %s", 
                                                model_name, str(e)
                                            )
                                            import re
                                            # Try to extract JSON from response
                                            json_match = re.search(r'\{.*\}|\[.*\]', raw_text, re.DOTALL)
                                            if json_match:
                                                try:
                                                    return json_lib.loads(json_match.group())
                                                except:
                                                    pass
                                            return {}
                                    else:
                                        return raw_text.strip()
                        
                        # Check for safety blocking
                        finish_reason = candidates[0].get('finishReason') if candidates else None
                        if finish_reason == 'SAFETY':
                            _logger.warning("Gemini API blocked content for safety reasons")
                            continue
                    
                    elif res.status_code == 429:
                        # Rate limiting - intelligent backoff
                        retry_after = res.headers.get('Retry-After')
                        try:
                            sleep_seconds = min(max(int(retry_after or 0), 5), 120)
                        except (TypeError, ValueError):
                            # Exponential backoff with jitter
                            base_delay = 5 * (2 ** attempt)
                            jitter = time.time() % 1  # Random component
                            sleep_seconds = min(base_delay + jitter, 60)
                        
                        _logger.warning(
                            "Gemini API rate limited (429) for %s (attempt %s/%s). "
                            "Sleeping %ss before retry...",
                            model_name, attempt + 1, max_retries, sleep_seconds
                        )
                        time.sleep(sleep_seconds)
                        
                        # On rate limit, try next model after first retry
                        if attempt == 0 and model_idx < len(models_to_try) - 1:
                            break
                        continue
                    
                    elif res.status_code in (400, 404):
                        # Model not available or bad request - try next model
                        _logger.warning(
                            "Gemini API error %s for model %s: %s",
                            res.status_code, model_name, res.text[:200]
                        )
                        break
                    
                    else:
                        _logger.warning(
                            "Gemini API HTTP %s (%s, attempt %s/%s): %s",
                            res.status_code, model_name, attempt + 1, max_retries, res.text[:300]
                        )
                        
                        # For server errors, retry with delay
                        if res.status_code >= 500 and attempt < max_retries - 1:
                            time.sleep(2 ** attempt)
                            continue
                        else:
                            break

                except requests.exceptions.Timeout:
                    _logger.warning(
                        "Gemini API timeout for %s (attempt %s/%s, timeout=%ss)",
                        model_name, attempt + 1, max_retries, timeout
                    )
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Short delay before retry
                        continue
                    else:
                        break
                        
                except Exception as err:
                    _logger.warning(
                        "Gemini API call failed for %s (attempt %s/%s): %s",
                        model_name, attempt + 1, max_retries, str(err)
                    )
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    else:
                        break

        _logger.error("All Gemini models failed for OCR request")
        return {} if response_json else ""

    def _render_page_image(self, page, dpi=150, preprocess=False):
        """Render a *fitz* page to a PIL Image.

        When *preprocess* is True the image is converted to grayscale and
        enhanced with contrast (1.8×) and sharpness (2.0×) — useful for
        scanned tables with narrow cells.
        """
        from PIL import Image, ImageEnhance

        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        if preprocess:
            img = img.convert('L')
            img = ImageEnhance.Contrast(img).enhance(1.8)
            img = ImageEnhance.Sharpness(img).enhance(2.0)
        return img

    @staticmethod
    def _img_to_b64(pil_img):
        """Convert a PIL Image to a base64-encoded JPEG string."""
        buf = io.BytesIO()
        pil_img.save(buf, format='JPEG', quality=92)
        return base64.b64encode(buf.getvalue()).decode('ascii')

    @staticmethod
    def _split_image_vertical(img, n_parts, overlap_px=20):
        """Split a PIL image into *n_parts* vertical strips with overlap."""
        width, height = img.size
        part_width = width // n_parts
        strips = []
        for i in range(n_parts):
            left = max(0, i * part_width - overlap_px) if i > 0 else 0
            right = min(width, (i + 1) * part_width + overlap_px) if i < n_parts - 1 else width
            strips.append(img.crop((left, 0, right, height)))
        return strips

    @staticmethod
    def _is_similar_page(ref_size, check_size, tolerance=0.05):
        """Return True if two (w, h) tuples are within *tolerance* of each other."""
        w_ratio = abs(ref_size[0] - check_size[0]) / max(ref_size[0], 1)
        h_ratio = abs(ref_size[1] - check_size[1]) / max(ref_size[1], 1)
        return w_ratio <= tolerance and h_ratio <= tolerance

    # ── Page Layout Classification ─────────────────────────────────────────

    def _classify_page_layout(self, page_image_b64, api_key):
        """Classify a page's layout using Gemini Vision at low resolution.

        Returns a dict::

            {
                "layout_type": "wide_table" | "simple_table" | "prose" | "form" | "mixed",
                "estimated_columns": int,
                "has_narrow_cells": bool,
                "column_headers": [str, ...]
            }

        Falls back to ``"prose"`` when classification fails.
        """
        CLASSIFY_PROMPT = (
            "Bạn là hệ thống phân tích bố cục tài liệu. Phân tích hình ảnh trang "
            "tài liệu này và trả về JSON với các field:\n"
            '{\n'
            '  "layout_type": "wide_table" | "simple_table" | "prose" | "form" | "mixed",\n'
            '  "estimated_columns": <int, số cột ước lượng, 0 nếu không phải bảng>,\n'
            '  "has_narrow_cells": <bool, có ô chứa ký hiệu ngắn 1-3 ký tự không>,\n'
            '  "column_headers": [<danh sách tên cột đọc được, rỗng nếu không phải bảng>]\n'
            '}\n\n'
            "Định nghĩa layout_type:\n"
            '- "wide_table": bảng >= 6 cột HOẶC có ô ký hiệu ngắn (1-3 ký tự).\n'
            '- "simple_table": bảng < 6 cột, không có ô ký hiệu ngắn.\n'
            '- "prose": văn bản đoạn văn thuần, không bảng.\n'
            '- "form": biểu mẫu có cặp label + giá trị điền.\n'
            '- "mixed": trang có cả bảng và đoạn văn.\n\n'
            "Trả về ĐÚNG JSON, không markdown, không giải thích."
        )

        fallback = {
            'layout_type': 'prose',
            'estimated_columns': 0,
            'has_narrow_cells': False,
            'column_headers': [],
        }

        try:
            result = self._gemini_call_vision(
                page_image_b64, CLASSIFY_PROMPT, api_key, response_json=True,
            )
            if isinstance(result, dict) and 'layout_type' in result:
                valid_types = ('wide_table', 'simple_table', 'prose', 'form', 'mixed')
                if result.get('layout_type') not in valid_types:
                    result['layout_type'] = 'prose'
                result.setdefault('estimated_columns', 0)
                result.setdefault('has_narrow_cells', False)
                result.setdefault('column_headers', [])
                return result
            _logger.warning("Classify returned unexpected format: %s", result)
            return fallback
        except Exception as e:
            _logger.warning("Page classification failed, falling back to prose: %s", str(e))
            return fallback

    # ── Per-layout OCR Pipeline Branches ───────────────────────────────────

    def _ocr_page_simple(self, page, api_key):
        """OCR pipeline for *prose* / *form* pages — single Gemini call."""
        img = self._render_page_image(page, dpi=150)
        img_b64 = self._img_to_b64(img)
        prompt = (
            "Trích xuất toàn bộ văn bản trong trang hình ảnh này sang định dạng "
            "markdown tiếng Việt. Giữ nguyên bố cục, đoạn văn và thứ tự nội dung."
        )
        return self._gemini_call_vision(img_b64, prompt, api_key)

    def _ocr_page_simple_table(self, page, api_key, column_headers):
        """OCR pipeline for *simple_table* pages (< 6 columns).

        Uses the *column_headers* discovered during classification to hint
        the OCR model, improving accuracy.
        """
        img = self._render_page_image(page, dpi=200)
        img_b64 = self._img_to_b64(img)

        if column_headers:
            cols_hint = ", ".join(column_headers)
            prompt = (
                f"Trích xuất bảng dữ liệu trong trang hình ảnh này sang markdown table. "
                f"Bảng có các cột: {cols_hint}. "
                "Giữ nguyên toàn bộ nội dung và văn bản đi kèm."
            )
        else:
            prompt = (
                "Trích xuất bảng dữ liệu trong trang hình ảnh này sang markdown table. "
                "Giữ nguyên toàn bộ nội dung và văn bản đi kèm."
            )
        return self._gemini_call_vision(img_b64, prompt, api_key)

    def _ocr_page_wide_table(self, page, api_key, classify_info):
        """OCR pipeline for *wide_table* pages — split, structured JSON, merge.

        The image is preprocessed (grayscale + contrast + sharpness), split
        into vertical strips, each strip is OCR'd as structured JSON, and the
        results are merged by ``row_index`` then converted to a Markdown table.
        Column names come entirely from *classify_info* — nothing is hardcoded.
        """
        estimated_cols = classify_info.get('estimated_columns', 6)
        column_headers = classify_info.get('column_headers', [])

        # Dynamic number of vertical splits
        if estimated_cols > 20:
            n_parts = 3
        elif estimated_cols >= 6:
            n_parts = 2
        else:
            n_parts = 1

        img = self._render_page_image(page, dpi=280, preprocess=True)

        if n_parts <= 1:
            # No splitting — single structured-JSON OCR call
            img_b64 = self._img_to_b64(img)
            prompt = self._build_wide_table_prompt(column_headers, 1, 1)
            rows = self._gemini_call_vision(img_b64, prompt, api_key, response_json=True)
            if isinstance(rows, list):
                return self._json_rows_to_markdown(rows, column_headers)
            return ""

        # Split image into N strips
        strips = self._split_image_vertical(img, n_parts, overlap_px=20)

        slices_data = []
        for i, strip in enumerate(strips):
            if i > 0:
                time.sleep(1)
            strip_b64 = self._img_to_b64(strip)
            prompt = self._build_wide_table_prompt(column_headers, i + 1, n_parts)
            result = self._gemini_call_vision(strip_b64, prompt, api_key, response_json=True)
            slices_data.append(result if isinstance(result, list) else [])

        merged = self._merge_sliced_rows(slices_data, column_headers)
        return self._json_rows_to_markdown(merged, column_headers)

    def _ocr_page_mixed(self, page, api_key):
        """OCR pipeline for *mixed* pages (tables + prose interleaved)."""
        img = self._render_page_image(page, dpi=200)
        img_b64 = self._img_to_b64(img)
        prompt = (
            "Trang tài liệu này chứa cả đoạn văn bản lẫn bảng dữ liệu. "
            "Trích xuất toàn bộ nội dung sang markdown, giữ nguyên thứ tự xuất hiện. "
            "Bảng dùng markdown table format. Văn bản giữ nguyên đoạn."
        )
        return self._gemini_call_vision(img_b64, prompt, api_key)

    # ── Wide-table JSON Helpers ────────────────────────────────────────────

    @staticmethod
    def _build_wide_table_prompt(column_headers, slice_idx, total_slices):
        """Build a dynamic OCR prompt for a wide-table image (or slice).

        Column names are injected from *column_headers* discovered at
        classification time — no document-specific names are hardcoded.
        """
        cols_str = ", ".join(column_headers) if column_headers else "(tự nhận diện từ ảnh)"

        slice_desc = ""
        if total_slices > 1:
            slice_desc = (
                f"Hình ảnh này là PHẦN {slice_idx}/{total_slices} (cắt dọc) của bảng. "
                "CHỈ trích xuất các cột BẠN NHÌN THẤY trong phần ảnh này.\n"
            )

        return (
            "Bạn là hệ thống OCR chuyên dụng cho bảng dữ liệu nhiều cột.\n"
            f"{slice_desc}"
            f"Bảng có các cột (theo thứ tự): {cols_str}\n\n"
            "Trích xuất MỌI hàng dữ liệu thành JSON array. Mỗi phần tử có:\n"
            '  - "row_index": số thứ tự hàng bắt đầu từ 1 (int)\n'
            '  - "cot": object chứa giá trị các cột hiện diện. '
            'Key = tên cột chính xác, value = nội dung ô (string, trống thì "").\n\n'
            "Trả về ĐÚNG JSON array, không markdown, không giải thích."
        )

    def _merge_sliced_rows(self, slices_data, column_headers):
        """Merge JSON row data from multiple vertical slices by ``row_index``.

        Each slice may contain a subset of columns.  Rows are aligned by
        their ``row_index`` field.  Missing matches are logged as warnings.
        """
        if not slices_data:
            return []
        if len(slices_data) == 1:
            return slices_data[0] if slices_data[0] else []

        merged = {}  # row_index -> merged cot dict

        for slice_idx, rows in enumerate(slices_data):
            if not isinstance(rows, list):
                continue
            for row in rows:
                idx = row.get('row_index')
                if idx is None:
                    continue
                idx = int(idx)
                if idx not in merged:
                    merged[idx] = {'row_index': idx, 'cot': {}}

                # Merge column values from 'cot' sub-object
                cot = row.get('cot', {})
                if isinstance(cot, dict):
                    for col, val in cot.items():
                        if col not in merged[idx]['cot'] or not merged[idx]['cot'][col]:
                            merged[idx]['cot'][col] = val

                # Also merge top-level keys matching known column headers
                for col in column_headers:
                    if col in row and col not in merged[idx]['cot']:
                        merged[idx]['cot'][col] = row[col]

        # Warn about gaps
        all_indices = sorted(merged.keys())
        if all_indices:
            expected = set(range(1, max(all_indices) + 1))
            missing = expected - set(all_indices)
            if missing:
                _logger.warning("[REVIEW] Missing row indices after merge: %s", sorted(missing))

        return [merged[i] for i in all_indices]

    @staticmethod
    def _json_rows_to_markdown(rows, column_headers):
        """Convert a list of row dicts to a Markdown table string.

        Uses *column_headers* (from classification) as the table header row.
        Each row dict is expected to have ``{"cot": {col: val, ...}}``.
        """
        if not rows or not column_headers:
            return ""

        md_header = '| ' + ' | '.join(column_headers) + ' |'
        md_sep = '| ' + ' | '.join(['---'] * len(column_headers)) + ' |'

        md_rows = []
        for row in rows:
            cot = row.get('cot', {})
            vals = [str(cot.get(col, '')).strip() for col in column_headers]
            md_rows.append('| ' + ' | '.join(vals) + ' |')

        return md_header + '\n' + md_sep + '\n' + '\n'.join(md_rows)

    # ── Main OCR Orchestrator ──────────────────────────────────────────────

    def _extract_pdf_ocr_gemini(self, file_content):
        """Extract text from a scanned PDF using an adaptive OCR pipeline.

        Pipeline overview:
          1. Classify page layout (wide_table / simple_table / prose / form / mixed)
             using a low-res Gemini call on the first 1-2 pages, cached for
             subsequent pages with similar dimensions.
          2. Branch to the appropriate per-layout OCR method.
          3. Combine page results with ``--- Trang N ---`` markers.

        No column names, split ratios, or document-specific keywords are
        hardcoded — all structural details are discovered by Gemini at runtime.
        """
        try:
            params = self.env['ir.config_parameter'].sudo()
            api_key = params.get_param('topic_chatbot.gemini_api_key')
            if not api_key:
                _logger.warning("Gemini API key not set, skipping OCR.")
                return ""

            import fitz

            doc_fitz = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc_fitz)
            extracted_pages = []

            # ── Step 1: Classify layout with caching ─────────────────────────
            classify_cache = {}  # pg_idx -> classify_info
            ref_classify = None
            ref_img_size = None

            pages_to_classify = [0]
            if total_pages > 1:
                pages_to_classify.append(1)

            safe_filename = (self.filename or '').encode('ascii', 'replace').decode('ascii')

            for pg_idx in pages_to_classify:
                page = doc_fitz[pg_idx]
                img = self._render_page_image(page, dpi=100)
                img_b64 = self._img_to_b64(img)

                classify_info = self._classify_page_layout(img_b64, api_key)
                classify_cache[pg_idx] = classify_info

                if ref_classify is None:
                    ref_classify = classify_info
                    ref_img_size = img.size

                _logger.info(
                    "Page %s of %s classified as: %s (cols=%s, narrow=%s, headers=%d)",
                    pg_idx + 1, safe_filename,
                    classify_info.get('layout_type'),
                    classify_info.get('estimated_columns'),
                    classify_info.get('has_narrow_cells'),
                    len(classify_info.get('column_headers', [])),
                )

            # Persist detected layout for the UI
            detected_layout = ref_classify.get('layout_type', 'prose') if ref_classify else 'prose'
            try:
                self.write({'layout_type': detected_layout})
            except Exception:
                pass  # never let metadata write break the OCR flow

            # ── Step 2: Process each page ─────────────────────────────────────
            for page_num, page in enumerate(doc_fitz, start=1):
                pg_idx = page_num - 1

                # Determine classify_info for this page
                if pg_idx in classify_cache:
                    page_classify = classify_cache[pg_idx]
                else:
                    # Check if dimensions match the reference page
                    pix_check = page.get_pixmap(dpi=100)
                    check_size = (pix_check.width, pix_check.height)
                    if ref_img_size and self._is_similar_page(ref_img_size, check_size):
                        page_classify = ref_classify
                    else:
                        img = self._render_page_image(page, dpi=100)
                        img_b64 = self._img_to_b64(img)
                        page_classify = self._classify_page_layout(img_b64, api_key)
                        classify_cache[pg_idx] = page_classify
                        _logger.info(
                            "Page %s reclassified as: %s", page_num,
                            page_classify.get('layout_type'),
                        )

                layout = page_classify.get('layout_type', 'prose')

                # Branch to appropriate pipeline with fallback
                try:
                    if layout in ('prose', 'form'):
                        page_text = self._ocr_page_simple(page, api_key)
                    elif layout == 'simple_table':
                        page_text = self._ocr_page_simple_table(
                            page, api_key, page_classify.get('column_headers', []),
                        )
                    elif layout == 'wide_table':
                        page_text = self._ocr_page_wide_table(page, api_key, page_classify)
                    elif layout == 'mixed':
                        page_text = self._ocr_page_mixed(page, api_key)
                    else:
                        page_text = self._ocr_page_simple(page, api_key)
                except Exception as page_err:
                    _logger.warning(
                        "OCR pipeline '%s' failed for page %s, falling back to simple: %s",
                        layout, page_num, str(page_err),
                    )
                    page_text = self._ocr_page_simple(page, api_key)

                if page_text:
                    extracted_pages.append(f"--- Trang {page_num} ---\n{page_text}")
                else:
                    _logger.warning("Could not OCR page %s of %s", page_num, safe_filename)

            return "\n\n".join(extracted_pages)
        except Exception as e:
            _logger.error("Gemini OCR error for %s: %s", self.filename, str(e))
            return ""

    @staticmethod
    def _format_excel_cell_value(val):
        """Format an Excel cell value cleanly into a string."""
        if val is None:
            return ""
        if isinstance(val, bool):
            return "True" if val else "False"
        if isinstance(val, (int, float)):
            if isinstance(val, int) or val == int(val):
                return str(int(val))
            return f"{val:.4f}".rstrip('0').rstrip('.')
        if hasattr(val, 'strftime'):  # datetime or date
            if hasattr(val, 'hour') and (val.hour != 0 or val.minute != 0 or val.second != 0):
                return val.strftime('%Y-%m-%d %H:%M:%S')
            return val.strftime('%Y-%m-%d')
        return str(val).strip()

    @staticmethod
    def _excel_column_name(col_idx):
        """Convert a 1-based column index to an Excel column label."""
        name = ""
        while col_idx:
            col_idx, rem = divmod(col_idx - 1, 26)
            name = chr(65 + rem) + name
        return name or "A"

    @staticmethod
    def _looks_like_raci_value(value):
        """Detect compact responsibility-matrix values (A/R/I/C/P/D/V/X/M or role action words)."""
        clean = (value or "").strip().upper()
        if not clean:
            return False
        if bool(re.match(r'^[ARICPDVXM*+](?:[/,+; ]+[ARICPDVXM*+])*$', clean)):
            return True
        raci_keywords = {
            'DUYỆT', 'PHÊ DUYỆT', 'THỰC HIỆN', 'KIỂM TRA', 'KÝ', 'ĐỀ XUẤT', 'THAM MƯU',
            'BÁO CÁO', 'THEO DÕI', 'XÁC NHẬN', 'THAM GIA', 'CHỦ TRÌ', 'PHỐI HỢP',
            'A', 'R', 'I', 'C', 'P', 'X', 'V'
        }
        return clean in raci_keywords or any(kw in clean for kw in ('PHÊ DUYỆT', 'THỰC HIỆN', 'KIỂM TRA', 'ĐỀ XUẤT'))

    def _build_excel_semantic_record(self, sheet_name, header, row):
        """Render one Excel data row as labelled facts for RAG retrieval.
        
        Fields are classified into business/permission/note categories.
        Only unclassified fields appear in 'Thông tin khác' to avoid duplication.
        """
        values = row.get('values', [])
        row_index = row.get('row_index')
        pairs = []
        pair_classified = []  # Parallel list: True if field is in a category section
        permission_pairs = []
        business_pairs = []
        note_pairs = []

        for idx, raw_value in enumerate(values):
            value = str(raw_value or "").replace('\n', ' ').strip()
            if not value:
                continue
            col_name = header[idx] if idx < len(header) and header[idx] else f"Cột {self._excel_column_name(idx + 1)}"
            col_ref = self._excel_column_name(idx + 1)
            labelled = (col_name, value, col_ref)
            pairs.append(labelled)

            col_lower = col_name.lower()
            is_classified = False

            if self._looks_like_raci_value(value) and re.search(r'[A-Za-zÀ-ỹĐđ]', col_name):
                permission_pairs.append(labelled)
                is_classified = True
            elif any(k in col_lower for k in ('ghi chú', 'quy định', 'lưu ý', 'căn cứ', 'hướng dẫn', 'hệ thống', 'odoo', 'thực hiện')):
                note_pairs.append(labelled)
                is_classified = True
            elif any(k in col_lower for k in ('nghiệp vụ', 'nội dung', 'quy trình', 'công việc', 'hạng mục', 'tên', 'mô tả', 'hoạt động')):
                business_pairs.append(labelled)
                is_classified = True
            elif len(value) > 8 and re.search(r'[A-Za-zÀ-ỹĐđ]', value) and not self._looks_like_raci_value(value):
                if not business_pairs:
                    business_pairs.append(labelled)
                else:
                    note_pairs.append(labelled)
                is_classified = True

            pair_classified.append(is_classified)

        if not pairs:
            return ""

        lines = [
            f"--- Sheet: {sheet_name} | Dòng: {row_index} ---",
        ]

        if business_pairs:
            for main_name, main_value, _ in business_pairs:
                lines.append(f"Nghiệp vụ / Nội dung ({main_name}): {main_value}")

        if permission_pairs:
            lines.append("Phân quyền / Trách nhiệm:")
            for col_name, value, col_ref in permission_pairs:
                lines.append(f"- {col_name} ({col_ref}): {value}")

        if note_pairs:
            lines.append("Quy định / Ghi chú thực hiện:")
            for col_name, value, col_ref in note_pairs:
                lines.append(f"- {col_name} ({col_ref}): {value}")

        # Only output fields NOT already classified above (avoid duplication)
        unclassified = [p for p, classified in zip(pairs, pair_classified) if not classified]
        if unclassified:
            lines.append("Thông tin khác:")
            for col_name, value, col_ref in unclassified:
                lines.append(f"- {col_name} ({col_ref}): {value}")

        return "\n".join(lines)

    def _detect_excel_header(self, raw_rows):
        """Detect header row and table structure from a list of rows in a sheet.
        
        Args:
            raw_rows: list of tuples (row_index, [cell_val1, cell_val2, ...])
            
        Returns:
            dict containing:
                - is_table: bool (True if table structure with header is detected)
                - header: list of str
                - prelude_lines: list of str (lines before header, like title or metadata)
                - rows: list of dict {'row_index': int, 'values': list of str}
                - raw_lines: list of str (fallback representation)
        """
        if not raw_rows:
            return {
                'is_table': False,
                'header': [],
                'prelude_lines': [],
                'rows': [],
                'raw_lines': []
            }

        # Filter out completely empty rows and convert cells to formatted strings.
        # Keep internal empty cells so column positions remain aligned with headers.
        cleaned_rows = []
        for r_idx, row in raw_rows:
            formatted = [self._format_excel_cell_value(c) for c in row]
            # Strip trailing empty cells
            while formatted and not formatted[-1]:
                formatted.pop()
            if any(formatted):
                cleaned_rows.append((r_idx, formatted))

        if not cleaned_rows:
            return {
                'is_table': False,
                'header': [],
                'prelude_lines': [],
                'rows': [],
                'raw_lines': []
            }

        raw_lines = [" | ".join(row) for _, row in cleaned_rows]

        # Scan for header candidate in the first 15 non-empty rows
        header_cand_idx = -1
        max_scan = min(len(cleaned_rows), 15)

        for i in range(max_scan):
            r_idx, row = cleaned_rows[i]
            non_empty = [c for c in row if c]
            if len(non_empty) < 2:
                # Likely a title, single banner, or single note
                continue

            # Check if cells are text-heavy (not pure numeric/date values)
            text_cells = 0
            for c in non_empty:
                # Text cell has alphabet characters or Vietnamese characters
                if re.search(r'[a-zA-ZàáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ]', c):
                    text_cells += 1

            text_ratio = text_cells / len(non_empty)
            # If >= 60% of non-empty cells contain text characters, candidate found!
            if text_ratio >= 0.6:
                header_cand_idx = i
                break

        if header_cand_idx == -1:
            # No clear header found (free text or pure numbers)
            return {
                'is_table': False,
                'header': [],
                'prelude_lines': [],
                'rows': [{'row_index': r_idx, 'values': row} for r_idx, row in cleaned_rows],
                'raw_lines': raw_lines
            }

        # Header found. Some business Excel sheets use multi-row/merged headers
        # (group names above concrete role names). Combine the nearby header rows
        # cell-by-cell so a value like "A" is later labelled with the full role.
        header_row_idx, header_raw = cleaned_rows[header_cand_idx]
        header_start_idx = header_cand_idx
        for j in range(header_cand_idx - 1, -1, -1):
            _, prev_row = cleaned_rows[j]
            non_empty_prev = [c for c in prev_row if c]
            if len(non_empty_prev) <= 1:
                break
            header_start_idx = j

        # Check forward rows that may also be sub-headers (e.g. row 2 is Group, row 3 is Sub-roles)
        header_end_idx = header_cand_idx
        for j in range(header_cand_idx + 1, min(len(cleaned_rows), header_cand_idx + 3)):
            _, next_row = cleaned_rows[j]
            non_empty_next = [c for c in next_row if c]
            if not non_empty_next:
                break

            # Guard: A row starting with a numeric sequence (e.g. STT 1, 2) or containing emails/dates is DATA, not a sub-header
            first_val = next_row[0].strip() if next_row else ""
            if first_val.isdigit() and len(first_val) <= 6:
                break
            if any('@' in c or re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', c) for c in non_empty_next):
                break

            avg_cell_len = sum(len(c) for c in non_empty_next) / len(non_empty_next)
            text_cells = sum(1 for c in non_empty_next if re.search(r'[A-Za-zÀ-ỹĐđ]', c))
            if text_cells / len(non_empty_next) >= 0.7 and avg_cell_len <= 35:
                raci_count = sum(1 for c in non_empty_next if self._looks_like_raci_value(c))
                if raci_count / len(non_empty_next) < 0.5:
                    header_end_idx = j
                else:
                    break
            else:
                break

        header_rows = [row for _, row in cleaned_rows[header_start_idx:header_end_idx + 1]]
        max_header_len = max(len(r) for r in header_rows + [header_raw])

        # Normalize header column names
        header = []
        for col_i in range(max_header_len):
            parts = []
            for hdr_row in header_rows:
                part = hdr_row[col_i].strip() if col_i < len(hdr_row) and hdr_row[col_i] else ""
                if part and part not in parts:
                    parts.append(part)
            name = " / ".join(parts) if parts else f"Cột {self._excel_column_name(col_i + 1)}"
            header.append(name)

        prelude_lines = [
            " | ".join(row)
            for _, row in cleaned_rows[:header_start_idx]
        ]

        data_rows = []
        for r_idx, row in cleaned_rows[header_end_idx + 1:]:
            # Pad or truncate row to match header length
            row_vals = list(row)
            if len(row_vals) < len(header):
                row_vals.extend([""] * (len(header) - len(row_vals)))
            elif len(row_vals) > len(header):
                row_vals = row_vals[:len(header)]
            data_rows.append({
                'row_index': r_idx,
                'values': row_vals
            })

        return {
            'is_table': True,
            'header': header,
            'prelude_lines': prelude_lines,
            'rows': data_rows,
            'raw_lines': raw_lines
        }

    def _extract_excel_structure(self, file_content):
        """Extract structured data from Excel files (.xlsx, .xls).
        
        Returns:
            list of dicts, each representing a sheet:
            [
                {
                    'sheet_name': str,
                    'is_empty': bool,
                    'is_table': bool,
                    'header': list of str,
                    'prelude_lines': list of str,
                    'rows': list of dict {'row_index': int, 'values': list of str},
                    'raw_lines': list of str
                }, ...
            ]
        """
        filename = (self.filename or '').lower()
        sheets_data = []

        # Try openpyxl first (.xlsx)
        if filename.endswith('.xlsx'):
            try:
                import openpyxl
                wb = openpyxl.load_workbook(
                    filename=io.BytesIO(file_content),
                    data_only=True,
                    read_only=False
                )
                for sheet_name in wb.sheetnames:
                    sheet = wb[sheet_name]
                    max_row = sheet.max_row or 0
                    max_col = sheet.max_column or 0

                    if max_row <= 1 and max_col <= 1:
                        # Empty check
                        val = sheet.cell(row=1, column=1).value if max_row == 1 and max_col == 1 else None
                        if val is None or not str(val).strip():
                            sheets_data.append({
                                'sheet_name': sheet_name,
                                'is_empty': True,
                                'is_table': False,
                                'header': [],
                                'prelude_lines': [],
                                'rows': [],
                                'raw_lines': []
                            })
                            continue

                    merged_master = {}
                    try:
                        for merged_range in sheet.merged_cells.ranges:
                            min_col, min_row, max_col_m, max_row_m = merged_range.bounds
                            master_value = sheet.cell(row=min_row, column=min_col).value
                            for rr in range(min_row, min(max_row_m + 1, max_row + 1)):
                                for cc in range(min_col, min(max_col_m + 1, max_col + 1)):
                                    if rr == min_row and cc == min_col:
                                        continue
                                    merged_master[(rr, cc)] = master_value
                    except Exception as e_merge:
                        _logger.debug("Failed reading merged cells in sheet %s: %s", sheet_name, str(e_merge))

                    raw_rows = []
                    for row_idx, row_cells in enumerate(sheet.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col), start=1):
                        row_values = []
                        for col_idx, cell in enumerate(row_cells, start=1):
                            val = cell.value
                            if val in (None, "") and merged_master and (row_idx, col_idx) in merged_master:
                                val = merged_master[(row_idx, col_idx)]
                            row_values.append(val)
                        raw_rows.append((row_idx, row_values))

                    merged_master.clear()
                    sheet_struct = self._detect_excel_header(raw_rows)
                    sheet_struct['sheet_name'] = sheet_name
                    sheet_struct['is_empty'] = False
                    sheets_data.append(sheet_struct)

                wb.close()
                return sheets_data
            except ImportError:
                _logger.warning("openpyxl not installed. Trying xlrd...")
            except Exception as e:
                _logger.warning("openpyxl extraction failed for %s: %s. Trying xlrd...", self.filename, str(e))

        # Fallback to xlrd for .xls and .xlsx fallback
        try:
            import xlrd
            from xlrd import xldate
            workbook = xlrd.open_workbook(file_contents=file_content)
            for sheet_idx in range(workbook.nsheets):
                sheet = workbook.sheet_by_index(sheet_idx)
                if sheet.nrows == 0:
                    sheets_data.append({
                        'sheet_name': sheet.name,
                        'is_empty': True,
                        'is_table': False,
                        'header': [],
                        'prelude_lines': [],
                        'rows': [],
                        'raw_lines': []
                    })
                    continue

                raw_rows = []
                for row_idx in range(sheet.nrows):
                    row_vals = sheet.row_values(row_idx)
                    row_types = sheet.row_types(row_idx)
                    formatted_row = []
                    for val, cell_type in zip(row_vals, row_types):
                        if val is None or val == "":
                            formatted_row.append("")
                        elif cell_type == xlrd.XL_CELL_DATE:
                            try:
                                date_val = xldate.xldate_as_datetime(val, workbook.datemode)
                                formatted_row.append(date_val)
                            except Exception:
                                formatted_row.append(val)
                        else:
                            formatted_row.append(val)
                    raw_rows.append((row_idx + 1, formatted_row))

                sheet_struct = self._detect_excel_header(raw_rows)
                sheet_struct['sheet_name'] = sheet.name
                sheet_struct['is_empty'] = False
                sheets_data.append(sheet_struct)

            return sheets_data
        except ImportError:
            raise UserError(
                f"Không thể xử lý tệp Excel '{self.filename}'. "
                "Vui lòng cài đặt thư viện cần thiết:\npip install openpyxl xlrd"
            )
        except Exception as e:
            raise UserError(f"Lỗi trích xuất tệp Excel '{self.filename}': {str(e)}")

    def _render_excel_structure_to_text(self, structure):
        """Render structured Excel sheets to a clean Markdown text document.
        
        Args:
            structure: list of sheet dicts returned by _extract_excel_structure
            
        Returns:
            str: Markdown formatted document text
        """
        if not structure:
            return ""

        text_sections = []
        for sheet in structure:
            sheet_name = sheet.get('sheet_name', 'Sheet')
            text_sections.append(f"--- Sheet: {sheet_name} ---")

            if sheet.get('is_empty'):
                text_sections.append("(Sheet trống)")
                continue

            if sheet.get('is_table'):
                # Output prelude lines if any
                for line in sheet.get('prelude_lines', []):
                    if line:
                        text_sections.append(line)

                # Output Markdown Table
                header = sheet.get('header', [])
                if header:
                    text_sections.append("| " + " | ".join(header) + " |")
                    text_sections.append("| " + " | ".join(["---"] * len(header)) + " |")

                for row in sheet.get('rows', []):
                    vals = [str(v).replace('\n', ' ').strip() for v in row.get('values', [])]
                    text_sections.append("| " + " | ".join(vals) + " |")

                # NOTE: Semantic records are NOT rendered here to avoid duplication in text_content.
                # They are generated separately in _chunk_excel_structure() for embedding child chunks.
            else:
                # Free-text or non-table sheet
                raw_lines = sheet.get('raw_lines', [])
                if raw_lines:
                    text_sections.extend(raw_lines)
                else:
                    text_sections.append("(Sheet không có nội dung)")

        return "\n".join(text_sections)

    def _detect_grouping_column(self, header, rows):
        """Detect primary categorical/grouping column from table headers and rows sample.
        Returns: col_index (0-based) or None if no clear grouping column is found (fallback).
        """
        if not header or not rows:
            return None

        total_rows = len(rows)
        grouping_keywords = (
            'phòng', 'ban', 'bộ phận', 'nhóm', 'loại', 'danh mục', 'trạng thái',
            'dự án', 'chủ đề', 'chi nhánh', 'khối', 'đơn vị', 'status',
            'department', 'category', 'type', 'group', 'branch', 'section'
        )

        candidates = []
        for idx, col_name in enumerate(header):
            c_clean = (col_name or '').lower()
            vals = [
                str(r.get('values', [])[idx]).strip()
                for r in rows
                if idx < len(r.get('values', [])) and str(r.get('values', [])[idx]).strip()
            ]
            unique_vals = set(vals)
            n_unique = len(unique_vals)

            # A grouping column typically has 2 <= unique_values <= 30
            # Allow higher unique ratio (up to 0.7) for small test/sheet samples (<= 20 rows)
            max_ratio = 0.7 if total_rows <= 20 else 0.45
            if 2 <= n_unique <= 30 and (n_unique / max(total_rows, 1)) <= max_ratio:
                score = 0
                if any(kw in c_clean for kw in grouping_keywords):
                    score += 10
                # Prefer columns appearing earlier (columns 0-4)
                score += max(0, 5 - idx)
                candidates.append((score, idx, col_name, n_unique))

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_idx, best_name, best_unique = candidates[0]
            if best_score >= 5:
                _logger.info(
                    "[EXCEL_GROUPING] Selected grouping column '%s' (col_idx=%d, %d unique values)",
                    best_name, best_idx, best_unique
                )
                return best_idx

        return None

    def _build_excel_sheet_summary(self, sheet_name, header, prelude, rows):
        """Generate a high-level Sheet Schema and Summary chunk.
        Enforces cardinality limit (<= EXCEL_MAX_CARDINALITY_DISPLAY = 25) to prevent chunk bloating.
        """
        if not header and not rows:
            return None

        total_rows = len(rows)
        total_cols = len(header)

        parts = [
            f"[SHEET_SUMMARY_SCHEMA] --- Sheet: {sheet_name} ---",
            f"Tổng quan bảng dữ liệu: {total_rows} dòng x {total_cols} cột.",
        ]
        if prelude:
            parts.append("Tiêu đề / Thông tin đầu bảng:")
            for p in prelude:
                parts.append(f"  {p}")

        parts.append("\nCấu trúc các cột & Dải giá trị tiêu biểu:")
        max_cardinality = getattr(self, 'EXCEL_MAX_CARDINALITY_DISPLAY', 25)

        for idx, col_name in enumerate(header):
            col_ref = self._excel_column_name(idx + 1)
            raw_vals = [
                str(r.get('values', [])[idx]).strip()
                for r in rows
                if idx < len(r.get('values', [])) and str(r.get('values', [])[idx]).strip()
            ]
            unique_vals = sorted(list(set(raw_vals)))
            n_unique = len(unique_vals)

            if not unique_vals:
                parts.append(f"- {col_ref} ({col_name}): (Cột trống hoặc không có dữ liệu)")
            elif n_unique <= max_cardinality:
                vals_str = ", ".join(unique_vals[:max_cardinality])
                parts.append(f"- {col_ref} ({col_name}) [{n_unique} giá trị]: {vals_str}")
            else:
                sample_str = ", ".join(unique_vals[:3])
                parts.append(f"- {col_ref} ({col_name}) [Độ phân tán cao: {n_unique} giá trị khác nhau; Mẫu: {sample_str}...]")

        return "\n".join(parts)

    def _chunk_excel_structure(self, structure, chunk_size=None, child_size=None):
        """Chunk structured Excel data into self-contained Parent-Child RAG groups.
        
        Features:
        - Sheet Summary & Schema Chunk: Top-level overview for macro intent & metadata routing.
        - Schema-Aware Grouping with Fallback: Groups by categorical column if detected; fallbacks to pure budget.
        - Content Budget with Soft Limits: Target 800-1200 chars for child chunks, with single-row overflow allowance.
        - Preserves semantic rows without mid-record cutting.
        """
        if not structure:
            return []

        chunk_size = chunk_size or self.EXCEL_PARENT_CHUNK_SIZE
        child_budget_min = getattr(self, 'EXCEL_CHILD_BUDGET_MIN', 800)
        child_budget_max = getattr(self, 'EXCEL_CHILD_BUDGET_MAX', 1200)

        groups = []

        for sheet in structure:
            if sheet.get('is_empty'):
                continue

            sheet_name = sheet.get('sheet_name', 'Sheet')

            if sheet.get('is_table'):
                header = sheet.get('header', [])
                prelude = sheet.get('prelude_lines', [])
                rows = sheet.get('rows', [])

                if not header or not rows:
                    content = self._render_excel_structure_to_text([sheet])
                    if content and len(content.strip()) > 10:
                        cleaned = content.strip()
                        children = self._split_into_child_chunks(cleaned, child_size=child_budget_min)
                        groups.append({'parent': cleaned, 'children': children})
                    continue

                # 1. Inject Sheet Summary / Schema Chunk as first chunk for this sheet
                sheet_summary = self._build_excel_sheet_summary(sheet_name, header, prelude, rows)
                if sheet_summary:
                    groups.append({
                        'parent': sheet_summary,
                        'children': [sheet_summary]
                    })

                # 2. Detect Schema Grouping Column (with fallback to None)
                group_col_idx = self._detect_grouping_column(header, rows)
                is_wide_table = len(header) > self.EXCEL_HEADER_COMPACT_THRESHOLD

                # Header block for Parent chunks
                full_header_parts = [f"--- Sheet: {sheet_name} ---"]
                if prelude:
                    full_header_parts.extend(prelude)
                full_header_parts.append("Các cột trong bảng:")
                for idx, col_name in enumerate(header, start=1):
                    full_header_parts.append(f"- {self._excel_column_name(idx)}: {col_name}")
                full_header_block = "\n".join(full_header_parts)

                # Header block for Child chunks (Compact mode for wide tables)
                if is_wide_table:
                    compact_header_parts = [f"--- Sheet: {sheet_name} ---"]
                    if prelude:
                        compact_header_parts.extend(prelude)
                    compact_header_parts.append(
                        f"Bảng có {len(header)} cột. Mỗi bản ghi dưới đây liệt kê tên cột và giá trị tương ứng."
                    )
                    header_block = "\n".join(compact_header_parts)
                else:
                    header_block = full_header_block

                # 3. Content Budget + Schema-Aware Packing
                # Parent tracking
                parent_records = []
                parent_len = len(full_header_block)

                def _flush_excel_parent(records_with_meta):
                    if not records_with_meta:
                        return
                    parent_text = full_header_block + "\n\n" + "\n\n".join([r['text'] for r in records_with_meta])

                    # Build children within this parent using Content Budget (Soft Target 800 - 1200)
                    children = []
                    child_buf = []
                    child_len = len(header_block)
                    current_group_tag = None
                    min_row_num = None
                    max_row_num = None

                    def _flush_child_buf():
                        nonlocal child_buf, child_len, current_group_tag, min_row_num, max_row_num
                        if not child_buf:
                            return
                        ctx_line = f"[Sheet: {sheet_name} | Dòng: {min_row_num} -> {max_row_num}"
                        if current_group_tag:
                            ctx_line += f" | Nhóm: {current_group_tag}"
                        ctx_line += "]"

                        child_text = f"{header_block}\n{ctx_line}\n\n" + "\n\n".join(child_buf)
                        children.append(child_text)
                        child_buf = []
                        child_len = len(header_block)
                        current_group_tag = None
                        min_row_num = None
                        max_row_num = None

                    for item in records_with_meta:
                        rec_text = item['text']
                        rec_group = item['group']
                        rec_row_idx = item['row_index']
                        rec_len = len(rec_text) + 2

                        # Check group boundary break: If grouping column exists and group value changed
                        group_changed = (
                            group_col_idx is not None
                            and current_group_tag is not None
                            and rec_group != current_group_tag
                        )
                        # Soft budget check: Buffer reached soft target (>= 800) and adding next record exceeds 1200
                        budget_reached = (child_len >= child_budget_min and (child_len + rec_len > child_budget_max))

                        if child_buf and (group_changed or budget_reached):
                            _flush_child_buf()

                        # Single-row overflow allowance: if single record itself exceeds budget_max, flush it as a standalone chunk
                        if not child_buf and rec_len > child_budget_max:
                            ctx_line = f"[Sheet: {sheet_name} | Dòng: {rec_row_idx}"
                            if rec_group:
                                ctx_line += f" | Nhóm: {rec_group}"
                            ctx_line += "]"
                            standalone_child = f"{header_block}\n{ctx_line}\n\n{rec_text}"
                            children.append(standalone_child)
                            continue

                        child_buf.append(rec_text)
                        child_len += rec_len
                        if current_group_tag is None:
                            current_group_tag = rec_group
                        if min_row_num is None:
                            min_row_num = rec_row_idx
                        max_row_num = rec_row_idx

                    if child_buf:
                        _flush_child_buf()

                    groups.append({
                        'parent': parent_text,
                        'children': children or [parent_text]
                    })

                for row in rows:
                    record_str = self._build_excel_semantic_record(sheet_name, header, row)
                    if not record_str:
                        continue
                    r_idx = row.get('row_index', 0)
                    r_group = None
                    if group_col_idx is not None and group_col_idx < len(row.get('values', [])):
                        r_group = str(row['values'][group_col_idx] or '').strip()

                    record_len = len(record_str) + 2
                    rec_meta = {'text': record_str, 'group': r_group, 'row_index': r_idx}

                    if parent_records and (parent_len + record_len > chunk_size):
                        _flush_excel_parent(parent_records)
                        parent_records = [rec_meta]
                        parent_len = len(full_header_block) + record_len
                    else:
                        parent_records.append(rec_meta)
                        parent_len += record_len

                if parent_records:
                    _flush_excel_parent(parent_records)

            else:
                # Non-table / Free-text sheet
                sheet_text = self._render_excel_structure_to_text([sheet])
                if sheet_text:
                    sub_groups = self._chunk_text(sheet_text, chunk_size=chunk_size, child_size=child_size)
                    groups.extend(sub_groups)

        return groups

    def _extract_excel_text(self, file_content):
        """Extract text content from Excel files (.xlsx, .xls)
        
        Features:
        - Support both modern (.xlsx) and legacy (.xls) formats
        - Uses structured extraction and Markdown table rendering
        - Preserves backwards compatibility for all callers
        """
        structure = self._extract_excel_structure(file_content)
        return self._render_excel_structure_to_text(structure)

    def _extract_docx_text(self, file_content):
        """Extract text from Word (.docx) files including paragraphs and tables.
        
        Strategy:
        1. Try python-docx (docx library)
        2. Fallback: Parse word/document.xml directly from the ZIP archive
        """
        import io
        text_parts = []

        # 1. Try python-docx
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            for para in doc.paragraphs:
                style_name = (para.style.name or '').strip().lower() if para.style else ''
                # Skip Table of Contents (TOC) entries
                if 'toc' in style_name:
                    continue
                p_text = para.text.strip()
                if not p_text:
                    continue
                
                # Check for heading style and add markdown header markers
                if 'heading 1' in style_name or style_name == 'title':
                    p_text = f"## {p_text}"
                elif 'heading 2' in style_name:
                    p_text = f"### {p_text}"
                elif 'heading 3' in style_name:
                    p_text = f"#### {p_text}"
                elif style_name.startswith('heading'):
                    p_text = f"#### {p_text}"
                
                text_parts.append(p_text)
            for table in doc.tables:
                table_rows = []
                for row in table.rows:
                    cells = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                    if any(cells):
                        table_rows.append("| " + " | ".join(cells) + " |")
                if table_rows:
                    text_parts.append("\n".join(table_rows))
            if text_parts:
                return "\n\n".join(text_parts)
        except ImportError:
            _logger.debug("python-docx not installed, using zipfile XML fallback for docx.")
        except Exception as e:
            _logger.warning("python-docx failed for %s: %s. Trying zipfile XML fallback...", self.filename, str(e))

        # 2. Fallback: Read word/document.xml from zipfile
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
                xml_content = zf.read('word/document.xml')
                tree = ET.fromstring(xml_content)
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for p in tree.iterfind('.//w:p', ns):
                    texts = [node.text for node in p.iterfind('.//w:t', ns) if node.text]
                    if texts:
                        text_parts.append("".join(texts).strip())
            return "\n\n".join([p for p in text_parts if p])
        except Exception as e:
            _logger.error("Failed to extract text from DOCX file %s: %s", self.filename, str(e))
            raise UserError(f"Không thể trích xuất nội dung từ tệp Word '{self.filename}': {str(e)}")

    def _extract_docx_images(self, file_content):
        """Extract valid embedded images from a Word (.docx) document as list of (image_index, raw_bytes, hash).
        
        Applies image_filter:
        - Skips WMF/EMF vector formats safely without throwing exceptions.
        - Skips small icons, avatars, and logos (<150x150 or <8KB).
        - Corrects EXIF rotation and downscales if >1600px.
        """
        valid_images = []
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_content))
            img_idx = 0
            for rel in doc.part.related_parts.values():
                if "image" in rel.content_type:
                    if not image_filter.is_supported_image_format(content_type=rel.content_type):
                        _logger.debug("Skipping unsupported vector/image format %s in doc %s", rel.content_type, self.id)
                        continue
                    raw_bytes = rel.blob
                    should_process, reason, processed_bytes, img_hash = image_filter.filter_and_preprocess_image(raw_bytes)
                    if should_process and processed_bytes:
                        valid_images.append((img_idx, processed_bytes, img_hash))
                    else:
                        _logger.debug("DOCX image %d skipped: %s", img_idx, reason)
                    img_idx += 1
        except Exception as e:
            _logger.warning("Error extracting embedded images from DOCX %s: %s", self.id, str(e))
        return valid_images

    def _extract_pdf_images(self, file_content):
        """Extract valid embedded images from a PDF document as list of (image_index, raw_bytes, hash).
        
        Applies image_filter:
        - Skips small icons/separators (<150x150 or <8KB).
        - Corrects rotation and downscales if >1600px.
        """
        valid_images = []
        try:
            import fitz
            doc_fitz = fitz.open(stream=file_content, filetype="pdf")
            img_idx = 0
            for page in doc_fitz:
                img_list = page.get_images(full=True)
                for img_info in img_list:
                    xref = img_info[0]
                    base_img = doc_fitz.extract_image(xref)
                    if not base_img or 'image' not in base_img:
                        continue
                    raw_bytes = base_img['image']
                    should_process, reason, processed_bytes, img_hash = image_filter.filter_and_preprocess_image(raw_bytes)
                    if should_process and processed_bytes:
                        valid_images.append((img_idx, processed_bytes, img_hash))
                    else:
                        _logger.debug("PDF image %d skipped: %s", img_idx, reason)
                    img_idx += 1
            doc_fitz.close()
        except Exception as e:
            _logger.warning("Error extracting embedded images from PDF %s: %s", self.id, str(e))
        return valid_images

    def _extract_txt_or_csv_text(self, file_content):
        for encoding in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1', 'gbk']:
            try:
                return file_content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file_content.decode('utf-8', errors='ignore')

    def _split_into_child_chunks(self, text, child_size=400, overlap=80):
        """Split a parent text block into smaller overlapping child chunks for vector search."""
        if not text:
            return []
        cleaned = text.strip()
        if len(cleaned) <= child_size + 100:
            return [cleaned]

        children = []
        start = 0
        text_len = len(cleaned)
        while start < text_len:
            end = min(start + child_size, text_len)
            if end < text_len:
                search_start = max(start + child_size // 2, end - 80)
                window = cleaned[search_start:end]
                newline_idx = window.rfind('\n')
                period_idx = window.rfind('. ')
                space_idx = window.rfind(' ')
                if newline_idx != -1:
                    end = search_start + newline_idx + 1
                elif period_idx != -1:
                    end = search_start + period_idx + 2
                elif space_idx != -1:
                    end = search_start + space_idx + 1
            child = cleaned[start:end].strip()
            if child and len(child) > 10:
                children.append(child)
            start = end - overlap
            if start >= text_len or end >= text_len:
                break
        return children or [cleaned]

    def _chunk_text(self, text, chunk_size=2000, overlap=400, child_size=400, child_overlap=80):
        """Split extracted text into Parent-Child RAG groups.

        Parent chunks preserve wide semantic boundaries, paragraphs, and markdown tables.
        Child chunks are granular sub-sections optimized for vector similarity search.

        Returns:
            list of dicts: [{'parent': str, 'children': [str, ...]}]
        """
        if not text:
            return []

        import re

        # Split by page / sheet markers
        pages = re.split(
            r'(?=(?:\n|\A)--- (?:Trang \d+|Sheet: [^\n]+) ---)', text,
        )
        parent_chunks = []

        for page in pages:
            page_content = page.strip()
            if not page_content:
                continue

            # Keep small pages intact for full RAG context
            if len(page_content) <= 2500:
                parent_chunks.append(page_content)
                continue

            lines = page_content.split('\n')

            # ── Pattern-based header detection (no hardcoded keywords) ───────
            is_header = [False] * len(lines)
            is_table_line = [False] * len(lines)

            for idx, line in enumerate(lines):
                stripped = line.strip()
                if not stripped.startswith('|'):
                    # Check markdown heading markers (## Heading, ### Heading, #### Heading)
                    if re.match(r'^#{2,4}\s+\S+', stripped):
                        is_header[idx] = True
                    continue
                is_table_line[idx] = True

                if '---' in stripped:
                    is_header[idx] = True
                    for back in range(idx - 1, -1, -1):
                        back_s = lines[back].strip()
                        if back_s.startswith('|') and '---' not in back_s:
                            is_header[back] = True
                        else:
                            break
                    continue

                if idx > 0:
                    prev = lines[idx - 1].strip()
                    if re.match(r'^--- (?:Trang \d+|Sheet: .+?) ---$', prev):
                        is_header[idx] = True

            # ── Pass 2: build parent chunks ─────────────────────────────────
            table_hdrs = []
            table_rows = []
            prose_buf = []
            in_table = False

            def _flush_table():
                if not table_rows:
                    return
                hdr_text = "\n".join(table_hdrs)
                n_hdr = len(table_hdrs)
                cur = [hdr_text] if hdr_text else []
                for r in table_rows:
                    cur.append(r)
                    if len("\n".join(cur)) > chunk_size:
                        parent_chunks.append("\n".join(cur))
                        cur = [hdr_text] if hdr_text else []
                if len(cur) > (n_hdr if hdr_text else 0):
                    parent_chunks.append("\n".join(cur))

            def _flush_prose():
                blob = "\n".join(prose_buf).strip()
                if not blob:
                    return
                if len(blob) <= chunk_size:
                    parent_chunks.append(blob)
                    return
                # Split large prose blob into chunks of ~chunk_size
                start = 0
                blob_len = len(blob)
                while start < blob_len:
                    end = min(start + chunk_size, blob_len)
                    if end < blob_len:
                        cut = blob.rfind('\n', start + chunk_size // 2, end)
                        if cut <= start:
                            cut = blob.rfind('. ', start + chunk_size // 2, end)
                            if cut > start:
                                cut += 2
                        if cut <= start:
                            cut = blob.rfind(' ', start + chunk_size // 2, end)
                            if cut > start:
                                cut += 1
                        if cut <= start:
                            cut = end
                    else:
                        cut = blob_len
                    chunk_piece = blob[start:cut].strip()
                    if chunk_piece:
                        parent_chunks.append(chunk_piece)
                    start = cut

            for idx, line in enumerate(lines):
                if is_header[idx]:
                    if prose_buf:
                        _flush_prose()
                        prose_buf = []
                    if is_table_line[idx]:
                        table_hdrs.append(line)
                        in_table = True
                    else:
                        if in_table:
                            _flush_table()
                            table_hdrs = []
                            table_rows = []
                            in_table = False
                        prose_buf.append(line)
                elif in_table and is_table_line[idx]:
                    table_rows.append(line)
                else:
                    if in_table:
                        _flush_table()
                        table_hdrs = []
                        table_rows = []
                        in_table = False
                    prose_buf.append(line)

            if in_table:
                _flush_table()
            if prose_buf:
                _flush_prose()

        # Fallback to sliding-window chunker if no parent chunks generated
        if not parent_chunks:
            start = 0
            text_len = len(text)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                if end < text_len:
                    search_start = max(start + chunk_size // 2, end - 200)
                    window = text[search_start:end]
                    newline_idx = window.rfind('\n')
                    period_idx = window.rfind('. ')
                    space_idx = window.rfind(' ')
                    if newline_idx != -1:
                        end = search_start + newline_idx + 1
                    elif period_idx != -1:
                        end = search_start + period_idx + 2
                    elif space_idx != -1:
                        end = search_start + space_idx + 1

                chunk = text[start:end].strip()
                if chunk:
                    parent_chunks.append(chunk)
                start = end - overlap
                if start >= text_len or end >= text_len:
                    break

        groups = []
        for p in parent_chunks:
            p_clean = p.strip()
            if len(p_clean) > 10:
                children = self._split_into_child_chunks(p_clean, child_size=child_size, overlap=child_overlap)
                groups.append({'parent': p_clean, 'children': children or [p_clean]})
        return groups

    def action_reprocess_document(self):
        """Action to reprocess a single document (useful after fixing errors)."""
        for doc in self:
            if doc.state == 'processing':
                raise UserError(f"Tài liệu '{doc.name}' đang được xử lý. Vui lòng đợi!")
            
            doc.write({
                'state': 'draft',
                'error_message': False,
                'text_content': False,
                'content_length': 0,
                'word_count': 0,
                'processing_time': 0.0
            })
        
        return self.action_process_document()

    def action_retry_failed_embeddings(self):
        """Retry generating embeddings ONLY for chunks that failed embedding in a background thread."""
        import threading
        for doc in self:
            if doc.state == 'processing':
                raise UserError(f"Tài liệu '{doc.name}' đang được xử lý. Vui lòng đợi!")

        db_name = self.env.cr.dbname
        uid = self.env.uid
        doc_ids = self.ids

        def _worker():
            import odoo
            with odoo.registry(db_name).cursor() as new_cr:
                env = api.Environment(new_cr, uid, {})
                for doc_id in doc_ids:
                    doc = env['topic_chatbot.document'].browse(doc_id)
                    if not doc.exists():
                        continue
                    failed_chunks = doc.chunk_ids.filtered(
                        lambda c: c.chunk_type in ('child', 'standard') and (not c.embedding or len(c.embedding.strip()) <= 10)
                    )
                    if not failed_chunks:
                        doc.write({'state': 'done', 'error_message': False})
                        new_cr.commit()
                        continue

                    from ..services import embedding_service
                    cfg = embedding_service.get_embedding_config(doc.env)
                    active_provider = cfg.get('provider') or 'gemini'
                    api_key = cfg.get('gemini_key') or ''
                    embedding_model = cfg.get('gemini_model') or 'gemini-embedding-2'

                    texts = [c.content for c in failed_chunks]
                    try:
                        embeddings = doc.env['topic_chatbot.chunk']._generate_embeddings_batch(
                            texts, api_key, embedding_model, chunk_records=failed_chunks, provider=active_provider, document_id=doc.id
                        )
                    except Exception as e:
                        _logger.error("Error retrying embeddings for doc %s: %s", doc.id, str(e))
                        embeddings = [None] * len(texts)

                    success_count = sum(1 for e in embeddings if e)
                    remaining_failed = len(doc.chunk_ids.filtered(lambda c: not c.embedding or len(c.embedding.strip()) <= 10))
                    if remaining_failed == 0:
                        doc.write({'state': 'done', 'error_message': False})
                        _logger.info("Doc %s (id=%s): All embeddings recovered. State -> done", doc.name, doc.id)
                    else:
                        doc.write({
                            'state': 'partial',
                            'error_message': f"Đã bổ sung embedding cho {success_count} đoạn. Còn {remaining_failed} đoạn chưa hoàn thành do hạn mức API."
                        })
                        _logger.info("Doc %s (id=%s): %d recovered, %d still pending.", doc.name, doc.id, success_count, remaining_failed)
                    new_cr.commit()

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bù Embeddings',
                'message': f"Đã khởi chạy tiến trình bù embeddings trong nền cho {len(self)} tài liệu. Kết quả sẽ tự động cập nhật.",
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_view_chunks(self):
        """Action to view chunks created from this document."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Text Chunks - {self.name}',
            'res_model': 'topic_chatbot.chunk',
            'view_mode': 'tree,form',
            'domain': [('document_id', '=', self.id)],
            'context': {
                'default_document_id': self.id,
                'default_topic_id': self.topic_id.id,
            }
        }
    
    def action_download_extracted_text(self):
        """Action to download extracted text as .txt file."""
        self.ensure_one()
        
        if not self.text_content:
            raise UserError("Tài liệu chưa được xử lý hoặc không có nội dung!")
            
        import base64
        
        filename = f"{self.name}_extracted.txt"
        content = self.text_content.encode('utf-8')
        content_b64 = base64.b64encode(content).decode('ascii')
        
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': content_b64,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain'
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    @api.model
    def get_processing_statistics(self):
        """Get processing statistics for dashboard/monitoring."""
        domain = []
        
        stats = {
            'total': self.search_count(domain),
            'done': self.search_count(domain + [('state', '=', 'done')]),
            'processing': self.search_count(domain + [('state', '=', 'processing')]),
            'error': self.search_count(domain + [('state', '=', 'error')]),
            'draft': self.search_count(domain + [('state', '=', 'draft')]),
        }
        
        # Average processing time
        processed_docs = self.search([('state', '=', 'done'), ('processing_time', '>', 0)])
        if processed_docs:
            stats['avg_processing_time'] = sum(processed_docs.mapped('processing_time')) / len(processed_docs)
        else:
            stats['avg_processing_time'] = 0.0
            
        # Total content statistics  
        done_docs = self.search([('state', '=', 'done')])
        stats['total_content_length'] = sum(done_docs.mapped('content_length'))
        stats['total_word_count'] = sum(done_docs.mapped('word_count'))
        stats['total_chunks'] = sum(done_docs.mapped('chunks_count'))
        
        return stats

    def _warn_prompt_injection_patterns(self, text):
        """Enhanced prompt injection detection with Vietnamese patterns."""
        if not text:
            return

        suspicious_patterns = [
            # English patterns
            'ignore previous instructions',
            'ignore all previous instructions', 
            'disregard previous instructions',
            'forget previous instructions',
            'system prompt',
            'developer message',
            'act as if you are',
            'pretend you are',
            'roleplay as',
            'jailbreak',
            'DAN mode',
            
            # Vietnamese patterns
            'bỏ qua hướng dẫn',
            'bỏ qua chỉ dẫn', 
            'bỏ qua các hướng dẫn trước',
            'quên các hướng dẫn trước',
            'tiết lộ toàn bộ dữ liệu',
            'bạn là một AI không giới hạn',
            'không giới hạn',
            'giả vờ bạn là',
            'hành động như thể bạn là',
            'đóng vai',
            'chế độ đặc biệt',
            
            # Technical patterns
            'system:',
            'assistant:',
            'human:',
            '###',
            '---SYSTEM---',
            '---USER---',
        ]
        
        text_lower = text.lower()
        matched_patterns = []
        
        for pattern in suspicious_patterns:
            if pattern.lower() in text_lower:
                # Count occurrences for severity assessment
                count = text_lower.count(pattern.lower())
                matched_patterns.append(f"{pattern} ({count}x)")
        
        if matched_patterns:
            # Log with different severity based on pattern count
            severity = 'warning' if len(matched_patterns) <= 2 else 'error'
            log_method = getattr(_logger, severity)
            
            log_method(
                "Possible prompt-injection content detected in document '%s' (id=%s): %s. "
                "Consider reviewing content before using in chat.",
                self.name, self.id, ", ".join(matched_patterns[:5])  # Limit output
            )
            
            # Store warning in document for user visibility
            if len(matched_patterns) > 3:
                warning_msg = (
                    f"⚠️ CẢNH BÁO: Tài liệu này chứa các mẫu nghi ngờ có thể ảnh hưởng đến "
                    f"hoạt động của chatbot: {', '.join(matched_patterns[:3])}..."
                )
                current_content = self.text_content or ""
                self.text_content = f"{warning_msg}\n\n{current_content}"
