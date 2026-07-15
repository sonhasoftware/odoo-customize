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
    datas = fields.Binary(string='File Content', required=True)
    filename = fields.Char(string='Filename')
    text_content = fields.Text(string='Extracted Text', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            record._process_document()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'datas' in vals or 'filename' in vals:
            for record in self:
                record._process_document()
        return res

    def _process_document(self):
        self.ensure_one()
        if not self.datas:
            return

        # Decode base64 file content
        try:
            file_content = base64.b64decode(self.datas)
        except Exception as e:
            _logger.error("Failed to decode base64 for document %s: %s", self.name, str(e))
            raise UserError("Invalid file encoding.")

        filename = (self.filename or '').lower()
        extracted_text = ""

        # Extract text based on file type
        try:
            if filename.endswith('.pdf'):
                extracted_text = self._extract_pdf_text(file_content)
            elif filename.endswith('.docx'):
                extracted_text = self._extract_docx_text(file_content)
            elif filename.endswith(('.txt', '.csv', '.json', '.xml', '.html', '.md')):
                extracted_text = file_content.decode('utf-8', errors='ignore')
            else:
                # Default fallback: try to decode as text
                extracted_text = file_content.decode('utf-8', errors='ignore')
        except Exception as e:
            _logger.error("Error extracting text from %s: %s", self.name, str(e))
            raise UserError(f"Failed to extract text from {self.name}: {str(e)}")

        self.write({'text_content': extracted_text})

        # Remove old chunks
        self.env['topic_chatbot.chunk'].search([('document_id', '=', self.id)]).unlink()

        # Create new chunks
        if extracted_text:
            chunks = self._chunk_text(extracted_text)
            chunk_vals = [{
                'topic_id': self.topic_id.id,
                'document_id': self.id,
                'content': chunk
            } for chunk in chunks]
            if chunk_vals:
                self.env['topic_chatbot.chunk'].create(chunk_vals)

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
