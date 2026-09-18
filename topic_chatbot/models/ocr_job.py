# -*- coding: utf-8 -*-
import base64
import gc
import logging
import psutil
import time
from datetime import timedelta
from odoo import api, fields, models
from ..services import image_filter, image_classifier, ocr_service, vision_service

_logger = logging.getLogger(__name__)

OLLAMA_COMPUTE_LOCK_KEY = 830917
STALE_OCR_PROCESSING_MINUTES = 10
MIN_RAM_AVAILABLE_BYTES = 3 * 1024 * 1024 * 1024  # 3GB


class TopicChatbotOcrJob(models.Model):
    _name = 'topic_chatbot.ocr_job'
    _description = 'Topic Chatbot OCR Processing Job'
    _order = 'create_date desc'

    name = fields.Char(
        string='Mã Tác vụ OCR',
        required=True,
        default=lambda self: self._default_name()
    )
    document_id = fields.Many2one(
        'topic_chatbot.document',
        string='Tài liệu liên quan',
        required=True,
        ondelete='cascade',
        index=True
    )
    state = fields.Selection([
        ('pending', 'Chờ xử lý'),
        ('processing', 'Đang xử lý'),
        ('done', 'Hoàn thành'),
        ('done_with_errors', 'Hoàn thành một phần (Có lỗi)'),
        ('failed', 'Thất bại')
    ], string='Trạng thái', default='pending', index=True, required=True)
    retry_count = fields.Integer(string='Số lần hoãn/thử lại', default=0)
    max_retries = fields.Integer(string='Thử lại tối đa', default=5)
    next_retry_at = fields.Datetime(string='Thời điểm thử lại kế tiếp', index=True)
    error_message = fields.Text(string='Thông báo lỗi / Tạm hoãn')

    images_count = fields.Integer(string='Tổng số ảnh', default=0)
    images_processed = fields.Integer(string='Số ảnh đã xong', default=0)
    processing_time = fields.Float(string='Thời gian xử lý (giây)', default=0.0)
    peak_ram_mb = fields.Float(string='Đỉnh RAM (MB)', default=0.0)
    provider_used = fields.Selection([
        ('paddleocr', 'PaddleOCR'),
        ('ollama_vision', 'Ollama Vision'),
        ('gemini_vision', 'Gemini Vision'),
        ('mixed', 'Đa luồng (Mixed / Dual-Route)'),
        ('none', 'Không OCR')
    ], string='Nhà cung cấp chính', default='mixed')

    image_line_ids = fields.One2many(
        'topic_chatbot.ocr_job_image_line',
        'job_id',
        string='Chi tiết từng ảnh'
    )

    def _default_name(self):
        return f"JOB/OCR/{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"

    def action_retry_now(self):
        """Allow admin to execute job immediately."""
        self.ensure_one()
        self.write({
            'state': 'processing',
            'next_retry_at': False,
            'error_message': False
        })
        self.env.cr.commit()
        self._execute_job_steps(self.env.cr)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tác vụ OCR',
                'message': f"Đã hoàn thành xử lý tác vụ OCR ({self.name}).",
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_process_ocr_jobs(self):
        """Cron worker: Pick 1 pending/stale job using FOR UPDATE SKIP LOCKED, process with per-image lock."""
        with self.env.registry.cursor() as dedicated_cr:
            # ── LỚP 1: Chọn Job an toàn với SKIP LOCKED và khôi phục Stale ────────
            query = """
                SELECT id, state FROM topic_chatbot_ocr_job
                WHERE (state = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= (now() at time zone 'UTC')))
                   OR (state = 'processing' AND write_date <= (now() at time zone 'UTC') - interval '%s minutes')
                ORDER BY id ASC 
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """
            dedicated_cr.execute(query, (STALE_OCR_PROCESSING_MINUTES,))
            res = dedicated_cr.fetchone()
            if not res:
                return

            job_id, initial_state = res[0], res[1]
            if initial_state == 'processing':
                _logger.warning("OCR Job %s bị gián đoạn quá %s phút. Phục hồi và tiếp tục xử lý các ảnh còn lại.",
                                job_id, STALE_OCR_PROCESSING_MINUTES)

            # Đánh dấu 'processing' ngay lập tức và commit để nhả row lock
            dedicated_cr.execute(
                "UPDATE topic_chatbot_ocr_job SET state = 'processing', write_date = (now() at time zone 'UTC') WHERE id = %s",
                (job_id,)
            )
            dedicated_cr.commit()

            # ── LỚP 2: Thực thi job trên dedicated environment ────────────────────
            dedicated_env = api.Environment(dedicated_cr, self.env.uid, self.env.context)
            job = dedicated_env['topic_chatbot.ocr_job'].browse(job_id)

            try:
                job._execute_job_steps(dedicated_cr)
            except Exception as job_err:
                _logger.error("Unexpected error executing OCR Job %s: %s", job_id, str(job_err))
                job.write({
                    'state': 'failed',
                    'error_message': f"Lỗi hệ thống: {str(job_err)}"
                })
                dedicated_cr.commit()

    def _execute_job_steps(self, dedicated_cr):
        """Execute OCR processing loop per image with in-loop RAM guard and per-image advisory lock."""
        self.ensure_one()
        doc = self.document_id
        if not doc or not doc.datas:
            self.write({'state': 'failed', 'error_message': 'Tài liệu không có dữ liệu (empty datas).'})
            dedicated_cr.commit()
            return

        lines_to_process = self.image_line_ids.filtered(lambda l: l.state == 'pending')
        if not lines_to_process:
            self._finalize_job_state(dedicated_cr)
            return

        # Re-extract raw image bytes on-the-fly from document to avoid storing duplicate blobs
        doc_content = base64.b64decode(doc.datas)
        raw_images_map = self._extract_raw_images_from_doc(doc, doc_content)

        start_time = time.time()
        initial_processed = len(self.image_line_ids.filtered(lambda l: l.state in ('done', 'failed')))

        for line in lines_to_process:
            # 1. In-Loop RAM Guard
            avail_ram = psutil.virtual_memory().available
            current_ram_mb = (psutil.virtual_memory().total - avail_ram) / (1024 ** 2)
            self.peak_ram_mb = max(self.peak_ram_mb or 0.0, current_ram_mb)

            if avail_ram < MIN_RAM_AVAILABLE_BYTES:
                _logger.warning("RAM khả dụng tụt xuống %.1f MB (<3000MB) khi đang xử lý ảnh %s (Job %s). Hoãn an toàn.",
                                avail_ram / (1024 ** 2), line.image_index, self.id)
                self.retry_count += 1
                if self.retry_count >= self.max_retries:
                    self.write({
                        'state': 'failed',
                        'error_message': f"Thất bại sau {self.max_retries} lần hoãn: Server liên tục thiếu RAM (<3GB)."
                    })
                else:
                    delay_secs = min(30 * (2 ** self.retry_count), 600)
                    self.write({
                        'state': 'pending',
                        'next_retry_at': fields.Datetime.now() + timedelta(seconds=delay_secs),
                        'error_message': f"Tạm hoãn tại ảnh {line.image_index}: RAM khả dụng {avail_ram / (1024 ** 2):.1f}MB < 3GB."
                    })
                dedicated_cr.commit()
                return

            # Match raw image bytes by (image_index, image_hash)
            img_bytes = raw_images_map.get(line.image_index)
            if not img_bytes or image_filter.compute_image_md5(img_bytes) != line.image_hash:
                # Try finding by hash in case index shifted
                img_bytes = None
                for candidate in raw_images_map.values():
                    if image_filter.compute_image_md5(candidate) == line.image_hash:
                        img_bytes = candidate
                        break

            if not img_bytes:
                line.write({
                    'state': 'failed',
                    'error_message': 'Không tìm thấy dữ liệu ảnh gốc tương ứng trong tài liệu.'
                })
                dedicated_cr.commit()
                continue

            # 2. Check MD5 Cache BEFORE calling any model
            cached_text = self.env['topic_chatbot.ocr_cache'].lookup_cache(line.image_hash)
            if cached_text:
                _logger.info("MD5 Cache HIT for image %s (hash %s)", line.image_index, line.image_hash)
                line.write({
                    'state': 'done',
                    'extracted_text': cached_text,
                    'processing_time': 0.01
                })
                self.images_processed = len(self.image_line_ids.filtered(lambda l: l.state in ('done', 'failed')))
                self.write({'write_date': fields.Datetime.now()})
                dedicated_cr.commit()
                continue

            # 3. Classify image to determine pipeline
            clf_result = image_classifier.classify_image(img_bytes)
            category = clf_result.get('category', 'text_table')
            line.category = category

            # 4. Acquire Per-Image Compute Lock (Blocking)
            img_start = time.time()
            res_text = None
            img_err = None

            dedicated_cr.execute("SELECT pg_advisory_lock(%s)", (OLLAMA_COMPUTE_LOCK_KEY,))
            try:
                if category == 'text_table':
                    res_text = ocr_service.call_ocr_engine(self.env, img_bytes)
                elif category == 'diagram':
                    res_text = vision_service.call_vision_ocr(self.env, img_bytes)
                elif category == 'mixed':
                    res_text = vision_service.call_dual_route_fusion(self.env, img_bytes)
                else:
                    res_text = ""
            except Exception as e:
                img_err = e
            finally:
                dedicated_cr.execute("SELECT pg_advisory_unlock(%s)", (OLLAMA_COMPUTE_LOCK_KEY,))

            img_duration = time.time() - img_start

            # 5. Save results outside lock scope
            if img_err:
                _logger.error("Lỗi xử lý ảnh %s (Job %s): %s", line.image_index, self.id, str(img_err))
                line.write({
                    'state': 'failed',
                    'category': category,
                    'error_message': str(img_err),
                    'processing_time': img_duration
                })
            else:
                line.write({
                    'state': 'done',
                    'category': category,
                    'extracted_text': res_text or "",
                    'processing_time': img_duration
                })
                # Persist into MD5 cache
                if res_text and res_text.strip():
                    self.env['topic_chatbot.ocr_cache'].save_cache(
                        line.image_hash, category, self.provider_used or 'mixed', res_text.strip()
                    )

            # Incremental updates to Job
            self.images_processed = len(self.image_line_ids.filtered(lambda l: l.state in ('done', 'failed')))
            self.processing_time = (self.processing_time or 0.0) + img_duration
            self.write({'write_date': fields.Datetime.now()})
            dedicated_cr.commit()
            gc.collect()

        self._finalize_job_state(dedicated_cr)

    def _finalize_job_state(self, dedicated_cr):
        """Evaluate completed image lines and set done, done_with_errors, or failed."""
        pending_remaining = self.image_line_ids.filtered(lambda l: l.state == 'pending')
        if not pending_remaining:
            total_cnt = len(self.image_line_ids)
            done_cnt = len(self.image_line_ids.filtered(lambda l: l.state == 'done'))
            failed_cnt = len(self.image_line_ids.filtered(lambda l: l.state == 'failed'))

            if done_cnt == total_cnt and total_cnt > 0:
                self.state = 'done'
                self.error_message = False
            elif failed_cnt == total_cnt:
                self.state = 'failed'
                self.error_message = f"100% hình ảnh ({total_cnt}/{total_cnt}) không thể trích xuất."
            else:
                self.state = 'done_with_errors'
                self.error_message = f"Hoàn thành {done_cnt}/{total_cnt} ảnh. Có {failed_cnt} ảnh bị lỗi."

            self._apply_results_to_document()
            dedicated_cr.commit()

    @api.model
    def _trigger_async_ocr_job(self, job_id):
        """Spawns a daemon thread to process an OCR job in the background immediately without blocking."""
        import threading
        import odoo

        db_name = self.env.cr.dbname
        uid = self.env.uid

        def _worker():
            with odoo.registry(db_name).cursor() as dedicated_cr:
                dedicated_env = api.Environment(dedicated_cr, uid, {})
                job = dedicated_env['topic_chatbot.ocr_job'].browse(job_id)
                if job.exists() and job.state in ('pending', 'processing'):
                    try:
                        job.write({'state': 'processing'})
                        dedicated_cr.commit()
                        _logger.info("Background OCR worker starting Job %s for document %s", job.id, job.document_id.id)
                        job._execute_job_steps(dedicated_cr)
                    except Exception as err:
                        _logger.error("Async OCR Job %s failed: %s", job_id, str(err))
                        try:
                            job.write({'state': 'failed', 'error_message': str(err)})
                            dedicated_cr.commit()
                        except Exception:
                            pass

        t = threading.Thread(target=_worker, name=f"TopicChatbot-AsyncOCR-{job_id}", daemon=True)
        t.start()
        _logger.info("Launched async OCR background thread for Job %s", job_id)

    def _apply_results_to_document(self):
        """Append extracted image content into document's text_content with atomic context markers,
        and incrementally create and embed image chunks into topic_chatbot.chunk.
        """
        doc = self.document_id
        if not doc:
            return

        image_blocks = []
        new_chunks = []
        
        # Determine starting sequence for incremental image chunks
        existing_chunks = self.env['topic_chatbot.chunk'].search([('document_id', '=', doc.id)])
        max_seq = max(existing_chunks.mapped('sequence') or [0])

        for line in self.image_line_ids.sorted(key=lambda l: l.image_index):
            if line.state == 'done' and line.extracted_text and line.extracted_text.strip():
                cat_name = line.category or 'text_table'
                icon = "📊" if cat_name == 'text_table' else ("🔄" if cat_name == 'diagram' else "🖼️")
                block = (
                    f"\n\n<!-- IMAGE_BLOCK_START id={line.image_index} hash={line.image_hash} -->\n"
                    f"> {icon} **[Hình ảnh {line.image_index + 1} - {cat_name.upper()}]:**\n"
                    f"> {line.extracted_text.strip().replace(chr(10), chr(10) + '> ')}\n"
                    f"<!-- IMAGE_BLOCK_END -->\n"
                )
                image_blocks.append(block)

                # Incremental chunk: check if this image chunk already exists
                chunk_marker = f"<!-- IMAGE_BLOCK_START id={line.image_index} "
                chunk_exists = existing_chunks.filtered(lambda c: chunk_marker in (c.content or ''))
                if not chunk_exists:
                    chunk_content = (
                        f"=== Tài liệu: {doc.name} - Hình ảnh {line.image_index + 1} ({cat_name.upper()}) ===\n"
                        f"{block.strip()}"
                    )
                    max_seq += 1
                    img_chunk = self.env['topic_chatbot.chunk'].create({
                        'topic_id': doc.topic_id.id,
                        'document_id': doc.id,
                        'sequence': max_seq,
                        'chunk_type': 'standard',
                        'content': chunk_content,
                    })
                    new_chunks.append(img_chunk)

        if image_blocks:
            current_text = doc.text_content or ""
            # Prevent appending duplicate blocks to text_content
            if "<!-- IMAGE_BLOCK_START" not in current_text:
                new_text = current_text + "\n\n" + "".join(image_blocks)
                doc.write({
                    'text_content': new_text,
                    'content_length': len(new_text),
                    'word_count': len(new_text.split())
                })
                _logger.info("Applied %d OCR image blocks to document %s (id=%s)", len(image_blocks), doc.name, doc.id)

        # Generate vector embeddings for newly created incremental image chunks
        if new_chunks:
            try:
                chunk_texts = [c.content for c in new_chunks]
                _logger.info("Generating embeddings for %d incremental image chunks for doc %s", len(new_chunks), doc.id)
                self.env['topic_chatbot.chunk']._generate_embeddings_batch(
                    chunk_texts, chunk_records=new_chunks, document_id=doc.id
                )
                doc.write({
                    'chunks_count': len(self.env['topic_chatbot.chunk'].search([('document_id', '=', doc.id)]))
                })
                _logger.info("Successfully created and embedded %d incremental image chunks for doc %s", len(new_chunks), doc.id)
            except Exception as emb_err:
                _logger.warning("Failed to generate embeddings for incremental image chunks on doc %s: %s", doc.id, str(emb_err))

        # Broadcast WebSocket notification so UI updates
        try:
            self.env['bus.bus']._sendone('broadcast', 'topic_chatbot.document/ocr_completed', {
                'document_id': doc.id,
                'ocr_job_id': self.id,
                'images_processed': len(image_blocks),
                'new_chunks_count': len(new_chunks),
                'name': doc.name,
            })
        except Exception as bus_err:
            _logger.debug("Could not send bus OCR completed notification: %s", str(bus_err))

    @api.model
    def _extract_raw_images_from_doc(self, doc, file_content):
        """Helper to re-extract raw image bytes indexed by appearance order."""
        filename = (doc.filename or '').lower()
        images_map = {}

        if filename.endswith('.pdf'):
            try:
                import fitz
                pdf_doc = fitz.open(stream=file_content, filetype="pdf")
                img_idx = 0
                for page in pdf_doc:
                    img_list = page.get_images(full=True)
                    for img_info in img_list:
                        xref = img_info[0]
                        base_img = pdf_doc.extract_image(xref)
                        if base_img and 'image' in base_img:
                            images_map[img_idx] = base_img['image']
                            img_idx += 1
                pdf_doc.close()
            except Exception as e:
                _logger.warning("PDF raw image re-extraction failed: %s", str(e))

        elif filename.endswith('.docx'):
            try:
                import docx
                import io
                word_doc = docx.Document(io.BytesIO(file_content))
                img_idx = 0
                for rel in word_doc.part.related_parts.values():
                    if "image" in rel.content_type:
                        if image_filter.is_supported_image_format(content_type=rel.content_type):
                            images_map[img_idx] = rel.blob
                            img_idx += 1
            except Exception as e:
                _logger.warning("DOCX raw image re-extraction failed: %s", str(e))

        return images_map


class TopicChatbotOcrJobImageLine(models.Model):
    _name = 'topic_chatbot.ocr_job_image_line'
    _description = 'Topic Chatbot OCR Job Image Line'
    _order = 'image_index asc'

    job_id = fields.Many2one(
        'topic_chatbot.ocr_job',
        string='Tác vụ OCR',
        required=True,
        ondelete='cascade',
        index=True
    )
    image_index = fields.Integer(string='Thứ tự ảnh', default=0)
    image_hash = fields.Char(string='MD5 Hash', size=32, index=True)
    category = fields.Selection([
        ('text_table', 'Văn bản / Bảng biểu'),
        ('diagram', 'Sơ đồ / Lưu đồ'),
        ('mixed', 'Hỗn hợp (Dual-Route)'),
        ('skipped', 'Bỏ qua (Quá nhỏ / WMF)')
    ], string='Phân loại ảnh')
    state = fields.Selection([
        ('pending', 'Chờ xử lý'),
        ('done', 'Hoàn thành'),
        ('failed', 'Lỗi')
    ], string='Trạng thái', default='pending', index=True)
    extracted_text = fields.Text(string='Nội dung trích xuất')
    error_message = fields.Text(string='Chi tiết lỗi (nếu có)')
    processing_time = fields.Float(string='Thời gian xử lý (giây)', default=0.0)
