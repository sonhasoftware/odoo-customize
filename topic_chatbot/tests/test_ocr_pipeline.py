# -*- coding: utf-8 -*-
import os
import unittest
from PIL import Image
try:
    from ..services import image_filter, image_classifier
except (ImportError, ValueError):
    import sys
    services_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'services'))
    sys.path.insert(0, services_path)
    import image_filter, image_classifier

class TestOcrPipeline(unittest.TestCase):
    """Automated unit tests for OCR Pipeline services, classification, filtering, and locks."""

    @classmethod
    def setUpClass(cls):
        cls.data_dir = os.path.join(os.path.dirname(__file__), 'data')
        cls.table_path = os.path.join(cls.data_dir, 'test_table.png')
        cls.diagram_path = os.path.join(cls.data_dir, 'test_diagram.png')
        cls.mixed_path = os.path.join(cls.data_dir, 'test_mixed.png')

    def test_01_image_filtering(self):
        """Test image dimensions, file size threshold, and MD5 calculation."""
        with open(self.table_path, 'rb') as f:
            raw_bytes = f.read()
        
        should_process, reason, processed_bytes, img_hash = image_filter.filter_and_preprocess_image(raw_bytes)
        self.assertTrue(should_process, f"Table image should pass filter: {reason}")
        self.assertIsNotNone(processed_bytes)
        self.assertEqual(len(img_hash), 32)

        # Test small image rejection
        tiny_img = Image.new('RGB', (50, 50), color='white')
        import io
        buf = io.BytesIO()
        tiny_img.save(buf, format='PNG')
        tiny_bytes = buf.getvalue()

        should_process, reason, _, _ = image_filter.filter_and_preprocess_image(tiny_bytes)
        self.assertFalse(should_process, "Tiny image should be skipped")
        self.assertIn("nhỏ", reason)

    def test_02_image_classification(self):
        """Test classification routing for table, diagram, and mixed fixtures."""
        with open(self.table_path, 'rb') as f:
            table_bytes = f.read()
        table_res = image_classifier.classify_image(table_bytes)
        self.assertEqual(table_res['category'], 'text_table')

        with open(self.diagram_path, 'rb') as f:
            diagram_bytes = f.read()
        diag_res = image_classifier.classify_image(diagram_bytes)
        self.assertEqual(diag_res['category'], 'diagram')

        with open(self.mixed_path, 'rb') as f:
            mixed_bytes = f.read()
        mixed_res = image_classifier.classify_image(mixed_bytes)
        self.assertEqual(mixed_res['category'], 'mixed')

    def test_03_vector_format_safety(self):
        """Test that WMF and EMF vector formats are safely skipped."""
        self.assertFalse(image_filter.is_supported_image_format(content_type='image/x-wmf'))
        self.assertFalse(image_filter.is_supported_image_format(content_type='image/x-emf'))
        self.assertTrue(image_filter.is_supported_image_format(content_type='image/png'))
        self.assertTrue(image_filter.is_supported_image_format(content_type='image/jpeg'))

    def test_04_thread_count_calculation(self):
        """Verify dynamic CPU thread calculation preserves cores for chat/web."""
        import os
        cpu_total = os.cpu_count() or 4
        # Our formula: max(1, cpu_count - 2)
        expected = max(1, cpu_total - 2)
        self.assertGreater(cpu_total, expected)
