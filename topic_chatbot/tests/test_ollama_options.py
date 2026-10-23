import unittest
from ..services.ollama_options import build_ollama_chat_options, build_ollama_chat_timeout


class TestOllamaContextOptions(unittest.TestCase):
    def test_document_chat_explicitly_reserves_input_context(self):
        options = build_ollama_chat_options()
        self.assertEqual(options['num_ctx'], 16384)
        self.assertGreater(options['num_ctx'], options['num_predict'])

    def test_configured_window_is_respected(self):
        self.assertEqual(build_ollama_chat_options('8192')['num_ctx'], 8192)

    def test_invalid_configuration_uses_default(self):
        for value in ('invalid', '', None, 0, -1):
            with self.subTest(value=value):
                self.assertEqual(build_ollama_chat_options(value)['num_ctx'], 16384)

    def test_context_and_output_bounded_for_small_window(self):
        options = build_ollama_chat_options(512)
        self.assertEqual(options['num_ctx'], 4096)
        self.assertLessEqual(options['num_predict'], options['num_ctx'] // 4)

    def test_context_allocation_has_upper_bound(self):
        self.assertEqual(build_ollama_chat_options(1000000)['num_ctx'], 32768)

    def test_cpu_prompt_read_timeout_does_not_change_connect_timeout(self):
        self.assertEqual(build_ollama_chat_timeout(), (10, 900))

    def test_configured_read_timeout_is_respected(self):
        self.assertEqual(build_ollama_chat_timeout('1200'), (10, 1200))

    def test_invalid_timeout_uses_default(self):
        self.assertEqual(build_ollama_chat_timeout('invalid'), (10, 900))

    def test_timeout_bounds(self):
        self.assertEqual(build_ollama_chat_timeout(1), (10, 30))
        self.assertEqual(build_ollama_chat_timeout(99999), (10, 1800))
