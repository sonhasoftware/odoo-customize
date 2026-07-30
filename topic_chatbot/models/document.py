# -*- coding: utf-8 -*-
import base64
import io
import logging
import zipfile
import xml.etree.ElementTree as ET
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Try importing PyPDF2
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

class TopicChatbotDocument(models.Model):
    _name = 'topic_chatbot.document'
    _description = 'Topic Document'

    name = fields.Char(string='Document Name', required=True)
    topic_id = fields.Many2one(
        'topic_chatbot.topic', 
        string='Topic', 
        required=True, 
        ondelete='cascade'
    )
    datas = fields.Binary(string='File Content', required=True, attachment=True)
    filename = fields.Char(string='Filename')
    text_content = fields.Text(string='Extracted Text', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error')
    ], string='Status', default='draft', required=True, readonly=True)

    @api.constrains('filename', 'datas')
    def _check_file_extension(self):
        ALLOWED_EXTENSIONS = ('.docx', '.txt')
        for doc in self:
            if doc.filename and doc.datas:
                filename_lower = doc.filename.lower()
                if not filename_lower.endswith(ALLOWED_EXTENSIONS):
                    raise UserError(
                        f"Tệp '{doc.filename}' không đúng định dạng. "
                        "Hệ thống chỉ chấp nhận tệp định dạng .docx hoặc .txt!"
                    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'datas' in vals or 'filename' in vals:
                vals['state'] = 'draft'
        records = super().create(vals_list)
        return records

    def write(self, vals):
        if 'datas' in vals or 'filename' in vals:
            vals['state'] = 'draft'
        res = super().write(vals)
        return res

    @api.model
    def _cron_process_documents(self):
        """Cron job to process draft documents."""
        documents = self.search([('state', '=', 'draft')], limit=5)
        for doc in documents:
            doc._process_document()

    def _process_document(self):
        for doc in self:
            if not doc.datas:
                doc.write({'state': 'done'})
                continue

            try:
                doc.write({'state': 'processing'})
                
                # Decode base64 file content
                file_content = base64.b64decode(doc.datas)
                filename = (doc.filename or '').lower()
                extracted_text = ""

                # Extract text based on file type (.docx and .txt only)
                if filename.endswith('.docx'):
                    extracted_text = doc._extract_docx_text(file_content)
                elif filename.endswith('.txt'):
                    extracted_text = file_content.decode('utf-8', errors='ignore')
                else:
                    raise UserError(
                        f"Tệp '{doc.filename}' không được hỗ trợ. "
                        "Hệ thống chỉ chấp nhận tệp định dạng .docx hoặc .txt!"
                    )

                doc.write({'text_content': extracted_text})
                doc._warn_prompt_injection_patterns(extracted_text)

                # Remove old chunks
                doc.env['topic_chatbot.chunk'].search([('document_id', '=', doc.id)]).unlink()

                # Create new chunks
                if extracted_text:
                    chunks = doc._chunk_text(extracted_text)
                    chunk_vals = [{
                        'topic_id': doc.topic_id.id,
                        'document_id': doc.id,
                        'sequence': index,
                        'content': chunk
                    } for index, chunk in enumerate(chunks, start=1)]
                    if chunk_vals:
                        doc.env['topic_chatbot.chunk'].create(chunk_vals)
                
                doc.write({'state': 'done'})
            except Exception as e:
                _logger.error("Error processing document %s: %s", doc.name, str(e))
                doc.write({'state': 'error'})

    def _extract_pdf_text(self, file_content):
        if not PdfReader:
            raise UserError("PyPDF2 library is not installed on the server. Please install it to parse PDF files.")
        
        try:
            reader = PdfReader(io.BytesIO(file_content))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except Exception as e:
            raise UserError(f"PDF extraction error: {str(e)}")

    def _extract_docx_text(self, file_content):
        try:
            docx = zipfile.ZipFile(io.BytesIO(file_content))
            xml_content = docx.read('word/document.xml')
            root = ET.fromstring(xml_content)
            
            # DOCX tags are namespace-prefixed
            namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = []
            
            for paragraph in root.iter(namespace + 'p'):
                texts = [node.text for node in paragraph.iter(namespace + 't') if node.text]
                if texts:
                    paragraphs.append("".join(texts))
            
            return "\n".join(paragraphs)
        except Exception as e:
            raise UserError(f"DOCX extraction error: {str(e)}")

    def _chunk_text(self, text, chunk_size=1000, overlap=200):
        chunks = []
        if not text:
            return chunks
            
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            
            # Find a word boundary near the end to avoid cutting words
            if end < text_len:
                last_space = -1
                for i in range(end, max(start, end - 100), -1):
                    if text[i] in ('\n', ' ', '\r', '\t'):
                        last_space = i
                        break
                if last_space != -1:
                    end = last_space
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                
            start = end - overlap
            if start >= text_len or end >= text_len:
                break
            if start < 0:
                start = 0
                
        return [c for c in chunks if len(c) > 10]

    def _warn_prompt_injection_patterns(self, text):
        if not text:
            return

        suspicious_patterns = [
            'ignore previous instructions',
            'ignore all previous instructions',
            'disregard previous instructions',
            'system prompt',
            'developer message',
            'bỏ qua hướng dẫn',
            'bỏ qua chỉ dẫn',
            'bỏ qua các hướng dẫn trước',
            'tiết lộ toàn bộ dữ liệu',
            'bạn là một AI không giới hạn',
            'không giới hạn',
        ]
        text_lower = text.lower()
        matched_patterns = [
            pattern for pattern in suspicious_patterns
            if pattern.lower() in text_lower
        ]
        if matched_patterns:
            _logger.warning(
                "Possible prompt-injection content detected in document %s (id=%s): %s",
                self.name,
                self.id,
                ", ".join(matched_patterns),
            )
