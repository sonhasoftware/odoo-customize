import unittest

from ..services.diagram_service import DiagramSpecError
from ..services.hybrid_pipeline import (
    build_gemini_handoff_prompt,
    collect_query_context,
    validate_and_normalize_diagram,
)


class TestHybridPipeline(unittest.TestCase):
    def _employee_context(self, truncated=False):
        return collect_query_context([{
            'name': 'query_odoo_data',
            'args': {'model': 'employees', 'domain': '[]'},
            'result': {
                'data': [
                    {
                        'id': 10,
                        'name': 'Nguyễn Quản Lý',
                        'job_title': 'Trưởng phòng',
                        'department_id': 'Phòng Công nghệ',
                        'parent_id': False,
                        'parent_id_record_id': False,
                    },
                    {
                        'id': 11,
                        'name': 'Trần Nhân Viên',
                        'job_title': 'Chuyên viên',
                        'department_id': 'Phòng Công nghệ',
                        'parent_id': 'Nguyễn Quản Lý',
                        'parent_id_record_id': 10,
                    },
                ],
                'truncated': truncated,
            },
        }])

    def test_handoff_marks_verified_database_as_source_of_truth(self):
        prompt = build_gemini_handoff_prompt('Bản tóm tắt', self._employee_context())
        self.assertIn('nguồn kiểm chứng cuối cùng', prompt)
        self.assertIn('parent_id_record_id', prompt)
        self.assertIn('Nguyễn Quản Lý', prompt)

    def test_duplicate_ollama_query_is_deduplicated(self):
        event = {
            'name': 'query_odoo_data',
            'args': {'model': 'employees', 'domain': '[]'},
            'result': [{'id': 10, 'name': 'Nguyễn Quản Lý'}],
        }
        context = collect_query_context([event, event])
        self.assertEqual(context['record_count'], 1)
        self.assertEqual(len(context['batches']), 1)

    def test_employee_nodes_and_edges_are_rebuilt_from_database(self):
        result = validate_and_normalize_diagram({
            'title': 'Sơ đồ phòng Công nghệ',
            'diagram_type': 'org_chart',
            'nodes': [
                {'id': '10', 'label': 'Tên bịa', 'subtitle': 'Giám đốc'},
                {'id': '11', 'label': 'Tên bịa khác', 'subtitle': 'Phó giám đốc'},
            ],
            'edges': [{'source': '11', 'target': '10'}],
        }, self._employee_context())

        self.assertEqual(result['nodes'][0]['label'], 'Nguyễn Quản Lý')
        self.assertEqual(result['nodes'][1]['label'], 'Trần Nhân Viên')
        self.assertEqual(result['nodes'][1]['subtitle'], 'Chuyên viên — Phòng Công nghệ')
        self.assertEqual(result['edges'], [{
            'source': '10', 'target': '11', 'label': 'Quản lý trực tiếp'
        }])

    def test_invented_employee_is_rejected(self):
        with self.assertRaises(DiagramSpecError):
            validate_and_normalize_diagram({
                'title': 'Sai',
                'diagram_type': 'org_chart',
                'nodes': [{'id': '999', 'label': 'Người không tồn tại'}],
                'edges': [],
            }, self._employee_context())

    def test_truncated_data_cannot_create_diagram(self):
        with self.assertRaises(DiagramSpecError):
            validate_and_normalize_diagram({
                'title': 'Toàn công ty',
                'diagram_type': 'org_chart',
                'nodes': [{'id': '10', 'label': 'Nguyễn Quản Lý'}],
                'edges': [],
            }, self._employee_context(truncated=True))


if __name__ == '__main__':
    unittest.main()
