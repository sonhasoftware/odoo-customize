# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import contextlib
import io
import importlib.util
import logging
import re

from odoo import models
from odoo.addons.ai.models.models import AI_SUPPORTED_IMG_TYPES
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter, to_pdf_stream, PdfReadError
from odoo.tools.image import ImageProcess

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    AI_MAX_PDF_PAGES = 5

    def _compute_pdf_content(self):
        """Compute the content of the PDF attachment."""
        self.ensure_one()

        def _has_pdfminer_six():
            return importlib.util.find_spec("pdfminer.high_level") is not None

        try:
            if not _has_pdfminer_six():
                _logger.warning("Attention: 'pdfminer.six' is not installed. PDF text extraction and AI sources context may not work properly.")
                return None

            from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter  # noqa: PLC0415
            from pdfminer.converter import TextConverter  # noqa: PLC0415
            from pdfminer.layout import LAParams  # noqa: PLC0415
            from pdfminer.pdfpage import PDFPage  # noqa: PLC0415
            logging.getLogger("pdfminer").setLevel(logging.CRITICAL)
        except ImportError:
            return None

        f = io.BytesIO(self.raw)
        resource_manager = PDFResourceManager()
        laparams = LAParams(
            line_margin=0.5,
            char_margin=2.0,
            word_margin=0.1,
            boxes_flow=0.5,
            detect_vertical=True,
        )

        with io.StringIO() as content, TextConverter(
            resource_manager,
            content,
            laparams=laparams
        ) as device:
            interpreter = PDFPageInterpreter(resource_manager, device)
            for page in PDFPage.get_pages(f):
                interpreter.process_page(page)

            buf = content.getvalue()

        return self._clean_pdf_content(buf)

    def _compute_pdf_content_via_ocr(self, max_pages=30):
        """
        Extract text from scanned/image-only PDFs using Gemini Vision API as OCR.
        Sends the entire PDF to Gemini in a single API call (Gemini natively supports PDF up to 20MB).
        Includes retry logic with exponential backoff for rate limiting (429 errors).

        :param max_pages: Maximum number of pages to process (default 30)
        :return: Extracted text content or None
        :rtype: str | None
        """
        import time as _time

        self.ensure_one()
        file_size_mb = len(self.raw) / (1024 * 1024)
        _logger.info("Attempting Gemini Vision OCR for scanned PDF: %s (%.1f MB)", self.name, file_size_mb)

        # Gemini supports PDF up to 20MB inline
        if file_size_mb > 20:
            _logger.warning("PDF too large for Gemini OCR (%.1f MB > 20 MB limit): %s", file_size_mb, self.name)
            return None

        try:
            from odoo.addons.ai.utils.llm_api_service import LLMApiService
            from odoo.addons.ai.utils.llm_providers import get_provider
        except ImportError:
            _logger.warning("Required modules not available for PDF OCR.")
            return None

        # If the PDF has too many pages, trim it to max_pages
        pdf_b64 = None
        try:
            from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter, PdfReadError
            pdf_stream = io.BytesIO(self.raw)
            reader = OdooPdfFileReader(pdf_stream, strict=False)
            num_pages = reader.numPages

            if num_pages > max_pages:
                _logger.info("PDF has %d pages, trimming to %d for OCR", num_pages, max_pages)
                writer = OdooPdfFileWriter()
                for i in range(max_pages):
                    writer.addPage(reader.getPage(i))
                trimmed = io.BytesIO()
                writer.write(trimmed)
                pdf_b64 = base64.b64encode(trimmed.getvalue()).decode()
            else:
                pdf_b64 = base64.b64encode(self.raw).decode()
        except Exception as e:
            _logger.warning("Failed to read/trim PDF, sending raw: %s", e)
            pdf_b64 = base64.b64encode(self.raw).decode()

        # Use a fast model for OCR - prefer gemini-2.5-flash-lite to avoid sharing quota with normal chat (gemini-3.5-flash)
        llm_model = 'gemini-2.5-flash-lite'


        try:
            api_service = LLMApiService(env=self.env, provider='google')
        except Exception as e:
            _logger.warning("Cannot initialize Gemini API for OCR: %s", e)
            return None

        # Send the entire PDF in a single API call
        body = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                    {"text": (
                        "Extract ALL text content from every page of this scanned document. "
                        "Preserve the original structure including tables, lists, and headings. "
                        "Output ONLY the extracted text, no commentary or summary. "
                        "If a page is blank, skip it."
                    )},
                ],
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 65536,
            },
        }

        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                _logger.info("Sending entire PDF to Gemini OCR (attempt %d/%d)...", attempt + 1, max_retries)
                response = api_service._request(
                    "post",
                    base_url="https://generativelanguage.googleapis.com/v1beta",
                    headers={},
                    endpoint=f"/models/{llm_model}:generateContent",
                    params={"key": api_service._get_api_token()},
                    body=body,
                    timeout=180,  # Large PDFs need more time
                )

                # Parse response
                all_text = []
                for candidate in response.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        text = part.get("text", "").strip()
                        if text:
                            all_text.append(text)

                if all_text:
                    result = "\n\n".join(all_text)
                    _logger.info(
                        "Gemini OCR extracted %d characters from %s (1 API call)",
                        len(result), self.name
                    )
                    return result

                _logger.warning("Gemini returned empty OCR result for %s", self.name)
                return None

            except Exception as e:
                error_str = str(e)
                is_rate_limit = '429' in error_str or 'quota' in error_str.lower()

                if is_rate_limit and attempt < max_retries - 1:
                    wait_time = 30 * (attempt + 1)  # 30s, 60s
                    _logger.info(
                        "Rate limited, waiting %ds before retry %d/%d for %s",
                        wait_time, attempt + 2, max_retries, self.name
                    )
                    _time.sleep(wait_time)
                    continue
                else:
                    _logger.warning("Gemini OCR failed for %s: %s", self.name, e)
                    return None

        return None

    @staticmethod
    def _is_valid_extracted_content(content):
        """Check if extracted content is meaningful (not just whitespace/control chars)."""
        if not content:
            return False
        # Remove control characters and whitespace
        cleaned = content.replace('\x0c', '').strip()
        if not cleaned or len(cleaned) < 10:
            return False
        words = cleaned.split()
        if len(words) <= 2:
            return False
        if len({w.lower() for w in words}) < 2:
            return False
        return True

    def _get_attachment_content(self):
        """
        Get the content of the attachment.
        For PDFs, prioritize content extracted via _compute_pdf_content over index_content.
        For scanned PDFs where text extraction fails, fall back to Gemini Vision OCR.
        For other file types, use index_content.
        :return: The content of the attachment or None if the content is invalid
        :rtype: str
        """
        self.ensure_one()
        # For PDF files, try to get content via _compute_pdf_content first
        if self.mimetype == 'application/pdf' and self.raw and self.raw.startswith(b'%PDF-'):
            pdf_content = self._compute_pdf_content()
            if self._is_valid_extracted_content(pdf_content):
                return pdf_content

            # Check index_content as second fallback
            if self._is_valid_extracted_content(self.index_content):
                return self.index_content

            # Final fallback: Gemini Vision OCR for scanned PDFs
            _logger.info("PDF text extraction failed for '%s', attempting Gemini Vision OCR...", self.name)
            ocr_content = self._compute_pdf_content_via_ocr()
            if self._is_valid_extracted_content(ocr_content):
                return ocr_content

            return False
        elif (self.mimetype == 'application/msword' or (self.name and self.name.lower().endswith('.doc'))) and self.raw:
            doc_text = None
            try:
                import tempfile
                import os
                import win32com.client
                import pythoncom
                fd, temp_path = tempfile.mkstemp(suffix='.doc')
                try:
                    os.write(fd, self.raw)
                    os.close(fd)
                    pythoncom.CoInitialize()
                    try:
                        word = win32com.client.Dispatch("Word.Application")
                        word.Visible = False
                        doc = word.Documents.Open(temp_path)
                        doc_text = doc.Range().Text
                        doc.Close()
                        word.Quit()
                    finally:
                        pythoncom.CoUninitialize()
                    if doc_text:
                        doc_text = doc_text.replace('\r\n', '\n').replace('\r', '\n').replace('\x07', '')
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except Exception as e:
                _logger.warning("Failed to extract .doc content using win32com: %s", e)
            if self._is_valid_extracted_content(doc_text):
                return doc_text
            return False
        else:
            # For non-PDF files, use index_content
            content = self.index_content

        # Validate the content
        if not content or len(content.split()) <= 2:
            return False
        # Check for reasonable content length and word variety
        words = content.split()
        if len(content.strip()) >= 10 and len({w.lower() for w in words}) >= 2:
            return content
        return None

    def _clean_pdf_content(self, buf):
        """
        Clean the PDF content by removing unwanted characters and formatting.
        """
        # Remove NUL characters that can cause PostgreSQL insertion errors
        buf = buf.replace('\x00', '')
        buf = buf.replace('\r\n', '\n').replace('\r', '\n')
        paragraphs = re.split(r'\n\s*\n', buf)
        paragraphs = [re.sub(r'[ \t]+', ' ', p.strip()) for p in paragraphs]
        return '\n'.join(paragraphs)

    def _setup_attachment_chunks(self, embedding_model, content=None):
        self.ensure_one()
        chunks = self._chunk_text(content)
        vals_list = []
        for chunk in chunks:
            if self.name:
                chunk = f"Attachment Name: {self.name}\n{chunk}"
            vals_list.append({
                'attachment_id': self.id,
                'content': chunk,
                'embedding_model': embedding_model,
            })

        self.env['ai.embedding'].create(vals_list)

    @staticmethod
    def _clean_text(text):
        """
        Clean up the text content while preserving meaningful structure.

        :param str text: Raw text content to clean
        :returns: Cleaned text content
        :rtype: str
        """
        # Remove NUL characters that can cause PostgreSQL insertion errors
        text = text.replace('\x00', '')
        text = text.replace('\r\n', '\n')

        # Split into lines and process
        lines = text.split('\n')
        result = []
        current_paragraph = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if current_paragraph:
                    result.append(' '.join(current_paragraph))
                    current_paragraph = []
                continue

            if stripped.endswith(':') or (len(stripped) < 120 and stripped.endswith('.')):
                if current_paragraph:
                    result.append(' '.join(current_paragraph))
                    current_paragraph = []
                result.append(stripped)
                continue

            current_paragraph.append(stripped)

        if current_paragraph:
            result.append(' '.join(current_paragraph))

        # Join with single newlines between paragraphs
        text = '\n'.join(result)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        return text.strip()

    @staticmethod
    def _chunk_text(text, chunk_size=1500, margin=200, min_chunk_size=1000, max_chunk_size=5000):
        """
        Split text into chunks based on character count with a hard maximum limit.
        The hard max limit is 5000 characters so that the chunks have enough context for the LLM to understand in case of large chunks.

        :param str text: The input text to chunk.
        :param int chunk_size: Target chunk size in characters.
        :param int margin: Allow flexibility in chunk sizes within chunk_size ± margin.
        :param int min_chunk_size: Minimum size a chunk should have before finalizing.
        :param int max_chunk_size: Hard maximum size limit that cannot be exceeded.
        :return: List of text chunks
        :rtype: list[str]
        """
        cleaned_text = IrAttachment._clean_text(text)
        chunks = []
        paragraphs = cleaned_text.split('\n')

        current_chunk = []
        current_length = 0

        def _add_chunk_enforcing_max_size(chunk_content):
            """Add a chunk, splitting it if it exceeds max_chunk_size."""
            if len(chunk_content) <= max_chunk_size:
                chunks.append(chunk_content)
            else:
                # Force split oversized chunks by words
                words = chunk_content.split()
                temp_chunk = []
                temp_length = 0
                for word in words:
                    word_length = len(word) + 1
                    if temp_length + word_length > max_chunk_size:
                        if temp_chunk:
                            chunks.append(" ".join(temp_chunk))
                        temp_chunk = [word]
                        temp_length = len(word)
                    else:
                        temp_chunk.append(word)
                        temp_length += word_length
                if temp_chunk:
                    chunks.append(" ".join(temp_chunk))

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue  # Skip empty lines

            para_length = len(para)

            # If current chunk is too small, try to merge with the next one
            if current_chunk and (current_length + para_length + 1 <= chunk_size + margin):
                current_chunk.append(para)
                current_length += para_length + 1
                continue

            # If the current chunk is large enough, store it
            if current_length >= chunk_size - margin:
                _add_chunk_enforcing_max_size(" ".join(current_chunk))
                current_chunk = [para]  # Start a new chunk
                current_length = para_length
            else:
                # If chunk is too small but para itself is too big, split it
                if para_length > chunk_size:
                    # First, store current chunk if it exists
                    if current_chunk:
                        _add_chunk_enforcing_max_size(" ".join(current_chunk))
                        current_chunk = []
                        current_length = 0
                    # Split the large paragraph by sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    temp_chunk = []
                    temp_length = 0

                    for sentence in sentences:
                        sent_length = len(sentence)

                        if temp_length + sent_length + 1 > chunk_size:
                            if temp_chunk:
                                _add_chunk_enforcing_max_size(" ".join(temp_chunk))
                            temp_chunk = [sentence]
                            temp_length = sent_length
                        else:
                            temp_chunk.append(sentence)
                            temp_length += sent_length + 1

                    if temp_chunk:
                        _add_chunk_enforcing_max_size(" ".join(temp_chunk))
                else:
                    current_chunk.append(para)
                    current_length += para_length + 1

        # Handle the last chunk
        if current_chunk:
            last_chunk_content = " ".join(current_chunk)
            if chunks and len(last_chunk_content) < min_chunk_size:
                # Try to merge with the previous chunk, but respect max_chunk_size
                if len(chunks[-1]) + len(last_chunk_content) + 1 <= max_chunk_size:
                    chunks[-1] += " " + last_chunk_content
                else:
                    # Can't merge, add as separate chunk
                    _add_chunk_enforcing_max_size(last_chunk_content)
            else:
                _add_chunk_enforcing_max_size(last_chunk_content)

        return chunks

    def _ai_read(self, fnames, files_dict):
        """When attachments are inserted in a prompt, one send the files (or indexed contents) to
        the LLMs.
        """
        if fnames:
            return super()._ai_read(fnames, files_dict)
        vals = []
        for attachment in self:
            if attachment.checksum in files_dict:
                vals.append({'id': attachment.id, 'file': files_dict[attachment.checksum]['file_ref']})
                continue
            file_ref = f'<file_#{len(files_dict) + 1}>'
            extension = attachment.mimetype.split('/')[-1]
            if extension == 'pdf' and not attachment.url:
                # Extract the X first / last pages of the PDFs
                reader = None
                with contextlib.suppress(PdfReadError):
                    reader = OdooPdfFileReader(to_pdf_stream(attachment), strict=False)
                if not reader or reader.numPages <= self.AI_MAX_PDF_PAGES:
                    b64_datas = attachment.datas.decode()
                else:
                    writer = OdooPdfFileWriter()
                    start_pages = self.AI_MAX_PDF_PAGES // 2
                    end_pages = self.AI_MAX_PDF_PAGES - start_pages
                    for p in (*range(start_pages), *range(reader.numPages - end_pages, reader.numPages)):
                        writer.addPage(reader.getPage(p))
                    out_buff = io.BytesIO()
                    writer.write(out_buff)
                    b64_datas = base64.b64encode(out_buff.getvalue()).decode()

                files_dict[attachment.checksum] = {
                    'mimetype': 'application/pdf',
                    'value': b64_datas,
                    'file_ref': file_ref,
                }
            elif extension in AI_SUPPORTED_IMG_TYPES and not attachment.url:
                raw_data = attachment.raw

                try:
                    image_process = ImageProcess(raw_data)
                    size = image_process.image.size
                    if max(size) > 1024:
                        raw_data = image_process \
                            .crop_resize(min(size[0], 1024), min(size[1], 1024), 0, 0) \
                            .image_quality(output_format='PNG')
                except Exception as e:  # noqa: BLE001
                    _logger.error("Image resize failed %s", e)

                files_dict[attachment.checksum] = {
                    'mimetype': attachment.mimetype,
                    'value': base64.b64encode(raw_data).decode(),
                    'file_ref': file_ref,
                }
            else:
                if not attachment.index_content or attachment.index_content == "application":
                    continue
                files_dict[attachment.checksum] = {
                    'mimetype': 'text/plain',
                    'value': attachment.index_content,
                    'file_ref': file_ref
                }
            vals.append({'id': attachment.id, 'file': file_ref})
        return vals, files_dict
