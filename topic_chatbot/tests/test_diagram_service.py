import unittest

from ..services.diagram_service import DiagramSpecError, render_svg


class TestDiagramService(unittest.TestCase):
    def test_org_chart_is_rendered_as_svg(self):
        result = render_svg({
            'title': 'Sơ đồ phòng Công nghệ',
            'diagram_type': 'org_chart',
            'nodes': [
                {'id': 'manager', 'label': 'Nguyễn Văn A', 'subtitle': 'Trưởng phòng'},
                {'id': 'employee', 'label': 'Trần Thị B', 'subtitle': 'Chuyên viên'},
            ],
            'edges': [{'source': 'manager', 'target': 'employee', 'label': 'Quản lý'}],
        })
        svg = result['svg_bytes'].decode('utf-8')
        self.assertIn('<svg', svg)
        self.assertIn('Nguyễn Văn A', svg)
        self.assertIn('marker-end="url(#arrow)"', svg)
        self.assertEqual(result['node_count'], 2)
        self.assertEqual(result['edge_count'], 1)

    def test_untrusted_text_is_escaped(self):
        result = render_svg({
            'title': '<script>alert(1)</script>',
            'diagram_type': 'flowchart',
            'nodes': [{'id': 'a', 'label': '<img src=x onerror=alert(1)>'}],
            'edges': [],
        })
        svg = result['svg_bytes'].decode('utf-8')
        self.assertNotIn('<script>', svg)
        self.assertNotIn('<img ', svg)
        self.assertIn('&lt;script&gt;', svg)

    def test_edges_to_unknown_nodes_are_removed(self):
        result = render_svg({
            'title': 'Luồng duyệt',
            'diagram_type': 'flowchart',
            'nodes': [{'id': 'a', 'label': 'Tạo đề nghị'}],
            'edges': [{'source': 'a', 'target': 'unknown', 'label': 'Không hợp lệ'}],
        })
        self.assertEqual(result['edge_count'], 0)

    def test_empty_diagram_is_rejected(self):
        with self.assertRaises(DiagramSpecError):
            render_svg({'title': 'Rỗng', 'diagram_type': 'flowchart', 'nodes': [], 'edges': []})

