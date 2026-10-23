import unittest
from types import SimpleNamespace

from ..services.document_routing import resolve_document_route


class TestDocumentRouting(unittest.TestCase):
    def topic(self, text, state='done'):
        return SimpleNamespace(document_ids=[
            SimpleNamespace(text_content=text, state=state)
        ])

    def test_prose_amount_and_approval_questions_use_document_rag(self):
        topic = self.topic(
            'Giám đốc duyệt khoản tạm ứng trên 20 triệu đồng.\n'
            'Hạn mức tạm ứng thông thường: 5 triệu đồng/người.'
        )
        self.assertEqual(resolve_document_route('STRUCTURED_DATA', topic), 'SEMANTIC_RAG')

    def test_ready_raci_table_keeps_structured_route(self):
        topic = self.topic('| Công việc | Giám đốc |\n| --- | --- |\n| Duyệt | A |')
        self.assertEqual(resolve_document_route('STRUCTURED_DATA', topic), 'STRUCTURED_DATA')

    def test_numeric_document_fact_does_not_count_unrelated_table(self):
        topic = self.topic(
            'OLLAMA_COMPUTE_LOCK_KEY = 830917\n\n'
            '| Tên | Giá trị |\n| --- | --- |\n| A | 79 |'
        )
        self.assertEqual(
            resolve_document_route(
                'STRUCTURED_DATA', topic,
                original_query='Tài liệu nêu khóa tính toán dùng cho Ollama có giá trị bao nhiêu?',
            ),
            'SEMANTIC_RAG',
        )

    def test_explicit_table_count_still_uses_structured_route(self):
        topic = self.topic('| Tên | Giá trị |\n| --- | --- |\n| A | 79 |')
        self.assertEqual(
            resolve_document_route('STRUCTURED_DATA', topic, original_query='Bảng có tổng số bao nhiêu dòng?'),
            'STRUCTURED_DATA',
        )

    def test_limit_amount_still_uses_document_fact_with_table_present(self):
        topic = self.topic('| Hạng mục | Số tiền |\n| --- | --- |\n| A | 79 |')
        self.assertEqual(
            resolve_document_route('STRUCTURED_DATA', topic, original_query='Hạn mức tạm ứng là bao nhiêu?'),
            'SEMANTIC_RAG',
        )

    def test_partial_table_remains_queryable(self):
        topic = self.topic('| Tên | Số tiền |\n| --- | --- |\n| A | 5 |', 'partial')
        self.assertEqual(resolve_document_route('STRUCTURED_DATA', topic), 'STRUCTURED_DATA')

    def test_unprocessed_table_is_not_a_ready_source(self):
        topic = self.topic('| Tên | Số tiền |\n| --- | --- |\n| A | 5 |', 'draft')
        self.assertEqual(resolve_document_route('STRUCTURED_DATA', topic), 'SEMANTIC_RAG')

    def test_empty_topic_uses_document_rag(self):
        self.assertEqual(resolve_document_route('STRUCTURED_DATA', SimpleNamespace(document_ids=[])), 'SEMANTIC_RAG')

    def test_prose_summary_does_not_require_spreadsheet_schema(self):
        self.assertEqual(resolve_document_route('SCHEMA_METADATA', self.topic('Quy trình tạm ứng.')), 'SEMANTIC_RAG')

    def test_schema_route_kept_for_table(self):
        topic = self.topic('| Tên | Số tiền |\n| --- | --- |\n| A | 5 |')
        self.assertEqual(resolve_document_route('SCHEMA_METADATA', topic), 'SCHEMA_METADATA')

    def test_semantic_route_does_not_inspect_documents(self):
        self.assertEqual(resolve_document_route('SEMANTIC_RAG', None), 'SEMANTIC_RAG')
