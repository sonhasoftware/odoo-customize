import unittest
from unittest.mock import patch

from ..services.chat_service import ChatService


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class TestOpenAIToolLoop(unittest.TestCase):
    def test_query_then_diagram_then_answer(self):
        responses = [
            _FakeResponse({'choices': [{'message': {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'id': 'call-query', 'type': 'function', 'function': {
                    'name': 'query_odoo_data',
                    'arguments': '{"model":"employees","fields":["id","name","parent_id"]}'
                }}]
            }}]}),
            _FakeResponse({'choices': [{'message': {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'id': 'call-diagram', 'type': 'function', 'function': {
                    'name': 'render_data_diagram',
                    'arguments': (
                        '{"title":"So do","diagram_type":"org_chart",'
                        '"nodes":[{"id":"manager","label":"A"},{"id":"employee","label":"B"}],'
                        '"edges":[{"source":"manager","target":"employee"}]}'
                    )
                }}]
            }}]}),
            _FakeResponse({'choices': [{'message': {
                'role': 'assistant', 'content': 'Sơ đồ đã được tạo.'
            }}]}),
        ]
        service = ChatService(None)
        original_execute = service._execute_tool

        def execute(name, args, env, topic):
            if name == 'query_odoo_data':
                return [{'id': 1, 'name': 'B', 'parent_id': 'A'}]
            return original_execute(name, args, env, topic)

        service._execute_tool = execute
        pipeline = {
            'openai_api_key': 'test-key',
            'openai_base_url': 'https://api.openai.com/v1',
            'openai_model': 'test-model',
            'system_instruction': 'Use tools.',
            'contents': [{'role': 'user', 'parts': [{'text': 'Vẽ sơ đồ tổ chức'}]}],
            'tools_list': [
                {'name': 'query_odoo_data', 'description': 'query', 'parameters': {'type': 'OBJECT'}},
                {'name': 'render_data_diagram', 'description': 'diagram', 'parameters': {'type': 'OBJECT'}},
            ],
        }

        with patch('odoo.addons.topic_chatbot.services.chat_service.requests.post', side_effect=responses) as post:
            reply, attachment, call_count = service._run_openai_chat(pipeline, None, None)

        self.assertEqual(post.call_count, 3)
        self.assertEqual(call_count, 2)
        self.assertEqual(reply, 'Sơ đồ đã được tạo.')
        self.assertEqual(attachment['attachment_mimetype'], 'image/svg+xml')
        self.assertTrue(attachment['attachment_data'])

