import base64
import io
import unittest
from unittest.mock import patch

from ..services import chat_attachment
from ..services import image_classifier, ocr_service, vision_service


class TestChatAttachment(unittest.TestCase):
    def payload(self, name, data):
        return {'name': name, 'data': base64.b64encode(data).decode('ascii')}

    def test_text_attachment_preserves_exact_fact(self):
        result = chat_attachment.prepare_chat_attachment(None, self.payload('policy.txt', 'Hạn mức: 5 triệu đồng.'.encode()), 'Hạn mức?')
        self.assertEqual(result['attachment_text'], 'Hạn mức: 5 triệu đồng.')
        self.assertEqual(result['attachment_name'], 'policy.txt')

    def test_pdf_attachment_extracts_page_text(self):
        import fitz
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), 'Odoo 17 attachment test')
        data = document.tobytes()
        document.close()
        result = chat_attachment.prepare_chat_attachment(None, self.payload('report.pdf', data), 'Phiên bản?')
        self.assertIn('Odoo 17 attachment test', result['attachment_text'])

    def test_spreadsheet_attachment_extracts_cells(self):
        from openpyxl import Workbook
        workbook = Workbook()
        workbook.active.append(['Mã', '4827'])
        stream = io.BytesIO()
        workbook.save(stream)
        result = chat_attachment.prepare_chat_attachment(None, self.payload('data.xlsx', stream.getvalue()), 'Mã?')
        self.assertIn('Mã | 4827', result['attachment_text'])

    def test_image_attachment_uses_ocr_result(self):
        from PIL import Image
        stream = io.BytesIO()
        Image.new('RGB', (200, 200), 'white').save(stream, format='PNG')
        with patch.object(image_classifier, 'classify_image', return_value={'category': 'text_table'}), \
             patch.object(ocr_service, 'call_ocr_engine', return_value='Mã ảnh: A-17'):
            result = chat_attachment.prepare_chat_attachment(None, self.payload('photo.png', stream.getvalue()), 'Mã?')
        self.assertIn('Mã ảnh: A-17', result['attachment_text'])

    def test_diagram_classification_keeps_ocr_as_authoritative_text(self):
        from PIL import Image
        stream = io.BytesIO()
        Image.new('RGB', (200, 200), 'white').save(stream, format='PNG')
        with patch.object(image_classifier, 'classify_image', return_value={'category': 'diagram'}), \
             patch.object(ocr_service, 'call_ocr_engine', return_value='SUN 2718'), \
             patch.object(vision_service, 'call_vision_ocr', return_value='Có chữ SUN 27/18'):
            result = chat_attachment.prepare_chat_attachment(None, self.payload('photo.png', stream.getvalue()), 'Mã?')
        self.assertIn('Văn bản OCR (nguồn ưu tiên cho chữ và số):\nSUN 2718', result['attachment_text'])
        self.assertIn('nếu chữ/số khác OCR, dùng OCR', result['attachment_text'])

    def test_rejects_unsupported_and_unsafe_paths(self):
        for name in ('notes.exe', '../notes.txt', 'folder\\notes.txt'):
            with self.subTest(name=name), self.assertRaises(chat_attachment.ChatAttachmentError):
                chat_attachment.prepare_chat_attachment(None, self.payload(name, b'hello'), 'Đọc?')

    def test_rejects_oversized_content_without_truncating(self):
        text = b'A' * (chat_attachment.MAX_TEXT_CHARS + 1)
        with self.assertRaises(chat_attachment.ChatAttachmentError):
            chat_attachment.prepare_chat_attachment(None, self.payload('long.txt', text), 'Đọc?')

    def test_rejects_invalid_base64(self):
        with self.assertRaises(chat_attachment.ChatAttachmentError):
            chat_attachment.prepare_chat_attachment(None, {'name': 'x.txt', 'data': '!!!!'}, 'Đọc?')
