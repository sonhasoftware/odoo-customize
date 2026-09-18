# -*- coding: utf-8 -*-
from odoo import api, fields, models


class TopicChatbotOcrCache(models.Model):
    _name = 'topic_chatbot.ocr_cache'
    _description = 'Topic Chatbot OCR Result Cache (MD5)'
    _order = 'create_date desc'

    image_hash = fields.Char(
        string='MD5 Hash',
        size=32,
        required=True,
        index=True,
        help="32-character hexadecimal MD5 hash of raw image bytes"
    )
    category = fields.Selection([
        ('text_table', 'Văn bản / Bảng biểu'),
        ('diagram', 'Sơ đồ / Lưu đồ'),
        ('mixed', 'Hỗn hợp (Dual-Route)'),
        ('skipped', 'Bỏ qua (Quá nhỏ / WMF)')
    ], string='Phân loại ảnh', required=True)
    provider_used = fields.Char(string='Nhà cung cấp đã dùng', help="PaddleOCR, Ollama Vision, Gemini, v.v.")
    extracted_text = fields.Text(string='Nội dung trích xuất')
    hit_count = fields.Integer(string='Số lần dùng lại', default=1)

    _sql_constraints = [
        ('uniq_image_hash', 'unique(image_hash)', 'MD5 Hash của ảnh phải là duy nhất trong bộ nhớ cache!')
    ]

    @api.model
    def lookup_cache(self, image_hash):
        """Find cached OCR text by MD5 hash.
        
        If found, increments hit_count and returns extracted_text.
        If not found, returns None.
        """
        if not image_hash:
            return None
        rec = self.search([('image_hash', '=', image_hash)], limit=1)
        if rec:
            try:
                rec.sudo().write({'hit_count': rec.hit_count + 1})
            except Exception:
                pass
            return rec.extracted_text or ""
        return None

    @api.model
    def save_cache(self, image_hash, category, provider_used, extracted_text):
        """Save new OCR result into cache, ignoring duplicates."""
        if not image_hash:
            return False
        rec = self.search([('image_hash', '=', image_hash)], limit=1)
        if rec:
            rec.sudo().write({
                'category': category,
                'provider_used': provider_used,
                'extracted_text': extracted_text,
                'hit_count': rec.hit_count + 1
            })
            return rec
        else:
            return self.create({
                'image_hash': image_hash,
                'category': category,
                'provider_used': provider_used,
                'extracted_text': extracted_text,
                'hit_count': 1
            })
