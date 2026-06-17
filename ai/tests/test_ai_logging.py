# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from odoo.addons.ai.models.ir_actions_server import _logger as tool_logger
from odoo.addons.ai.utils.ai_logging import _logger as ai_logger
from odoo.addons.ai.utils.llm_api_service import LLMApiService, _logger as service_logger
from odoo.addons.ai.utils.llm_providers import get_provider


@tagged("post_install", "-at_install")
class TestAILoggingIntegration(TransactionCase):
    def setUp(self):
        super().setUp()
        ai_agent_model = self.env.ref('ai.model_ai_agent')
        tool1 = self.env['ir.actions.server'].create({
            'name': 'AI: Get Employee Info',
            'state': 'code',
            'model_id': ai_agent_model.id,
            'use_in_ai': True,
            'code': """ai['result'] = 'Employee: John Doe'""",
            'ai_tool_description': 'Get information about an employee',
            'ai_tool_schema': json.dumps({
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "__end_message": {"type": "string"},
                },
                "required": ["employee_id", "__end_message"],
            }),
        })

        tool2 = self.env['ir.actions.server'].create({
            'name': 'AI: Update Employee Status',
            'state': 'code',
            'model_id': ai_agent_model.id,
            'use_in_ai': True,
            'code': """ai['result'] = 'Status updated'""",
            'ai_tool_description': 'Update employee status',
            'ai_tool_schema': json.dumps({
                "type": "object",
                "properties": {
                    "employee_id": {"type": "integer"},
                    "status": {"type": "string"},
                    "__end_message": {"type": "string"},
                },
                "required": ["employee_id", "status", "__end_message"],
            }),
        })

        self.tools = tool1 | tool2
        self.tool1_id = tool1.id
        self.tool2_id = tool2.id

    def _request_llm_test(self, llm_model, prompt):
        llm_services = LLMApiService(self.env, get_provider(self.env, llm_model))
        return llm_services.request_llm(
            llm_model=llm_model,
            system_prompts=[],
            user_prompts=[],
            inputs=[{'role': 'user', 'content': prompt}],
            tools=self.tools._get_ai_tools(),
        )

    def _create_mock_request(self, responses):
        """Create a mock request function that cycles through the given responses."""
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        return mock_request

    def test_sequential_tool_calls(self):
        """Test logging for sequential tool calls with multiple API calls.

        Verifies that when tools are called one after another (not in batch),
        the logging correctly tracks each API call and tool execution separately.
        """
        mock_request = self._create_mock_request([
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool1_id}",
                        "call_id": "call_1",
                        "arguments": '{"employee_id": 1, "__end_message": ""}',
                    },
                ],
            },
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool2_id}",
                        "call_id": "call_2",
                        "arguments": '{"employee_id": 1, "status": "active", "__end_message": ""}',
                    },
                ],
            },
            {
                "output": [
                    {"text": "All tasks completed."},
                ],
            },
        ])

        with patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request', side_effect=mock_request), \
            patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy_token'), \
            self.assertLogs(ai_logger, level='DEBUG') as mock_ai_logger, \
            self.assertLogs(tool_logger, level='DEBUG') as mock_tool_logger:

            response = self._request_llm_test("gpt-4o", "Get employee 1 info and update status to active")
            self.assertEqual(len(response), 1)

        self.assertEqual([r.msg for r in mock_tool_logger.records if r.levelname == 'DEBUG'], [
            "[AI Tool →] '%s' with args (%s)",
            "[AI Tool - %.2fs] Completed '%s'%s",
            "[AI Tool →] '%s' with args (%s)",
            "[AI Tool - %.2fs] Completed '%s'%s",
        ])
        self.assertEqual([r.msg for r in mock_ai_logger.records if r.levelname == 'DEBUG'], [
            "[AI Response] Starting generation for model '%s'",
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d - →] Received single tool call (%.2fs, %d tokens)',
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d - →] Received single tool call (%.2fs, %d tokens)',
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d] Completed (%.2fs, %d tokens)',
            '[AI Summary] Total: %.2fs | API calls: %d (%.2fs) | Tools: %d (%.2fs) | Tokens: %d (in: %d, out: %d) | Batches: %d',
        ])

    def test_parallel_tool_calls(self):
        """Test logging for parallel/batch tool calls.

        Verifies that when multiple tools are called in a single API response,
        they are logged as a batch with the ⚡ symbol and batch tracking.
        """
        mock_request = self._create_mock_request([
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool1_id}",
                        "call_id": "call_1",
                        "arguments": '{"employee_id": 1, "__end_message": ""}',
                    },
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool2_id}",
                        "call_id": "call_2",
                        "arguments": '{"employee_id": 1, "status": "active", "__end_message": ""}',
                    },
                ],
            },
            {
                "output": [
                    {"text": "All done."},
                ],
            },
        ])

        with patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request', side_effect=mock_request), \
            patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy_token'), \
            self.assertLogs(ai_logger, level='DEBUG') as mock_ai_logger, \
            self.assertLogs(tool_logger, level='DEBUG') as mock_tool_logger, \
            self.assertLogs(service_logger, level='DEBUG') as mock_service_logger:

            response = self._request_llm_test("gpt-4o", "Get employee 1 info and update status at the same time")
            self.assertEqual(len(response), 1)

        self.assertEqual([r.msg for r in mock_ai_logger.records if r.levelname == 'DEBUG'], [
            "[AI Response] Starting generation for model '%s'",
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d - ⚡] Received Batch #%d, %d tool calls (%.2fs, %d tokens)',
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d] Completed (%.2fs, %d tokens)',
            '[AI Summary] Total: %.2fs | API calls: %d (%.2fs) | Tools: %d (%.2fs) | Tokens: %d (in: %d, out: %d) | Batches: %d',
        ])
        self.assertEqual([r.msg for r in mock_tool_logger.records if r.levelname == 'DEBUG'], [
            "[AI Tool - Batch #%d ⚡] '%s' with args (%s)",
            "[AI Tool - Batch #%d - %.2fs] Completed '%s'%s",
            "[AI Tool - Batch #%d ⚡] '%s' with args (%s)",
            "[AI Tool - Batch #%d - %.2fs] Completed '%s'%s",
        ])
        self.assertEqual([r.msg for r in mock_service_logger.records if r.levelname == 'DEBUG'], [
            '[AI Tool Summary] Batch #%d completed, %d tool calls',
        ])

    def test_mixed_tool_calls(self):
        """Test logging for mixed parallel and sequential tool calls.

        Verifies correct logging when some tools are called in batch
        followed by individual tool calls in subsequent API responses.
        """
        mock_request = self._create_mock_request([
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool1_id}",
                        "call_id": "call_1",
                        "arguments": '{"employee_id": 1, "__end_message": ""}',
                    },
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool1_id}",
                        "call_id": "call_2",
                        "arguments": '{"employee_id": 2, "__end_message": ""}',
                    },
                ],
            },
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": f"action_{self.tool2_id}",
                        "call_id": "call_3",
                        "arguments": '{"employee_id": 1, "status": "reviewed", "__end_message": ""}',
                    },
                ],
            },
            {
                "output": [
                    {"text": "Done."},
                ],
            },
        ])

        with patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._request', side_effect=mock_request), \
            patch('odoo.addons.ai.utils.llm_api_service.LLMApiService._get_api_token', return_value='dummy_token'), \
            self.assertLogs(ai_logger, level='DEBUG') as mock_ai_logger, \
            self.assertLogs(tool_logger, level='DEBUG') as mock_tool_logger, \
            self.assertLogs(service_logger, level='DEBUG') as mock_service_logger:

            response = self._request_llm_test("gpt-4o", "Get info for employees 1 and 2, then update employee 1 status")
            self.assertEqual(len(response), 1)

        self.assertEqual([r.msg for r in mock_ai_logger.records if r.levelname == 'DEBUG'], [
            "[AI Response] Starting generation for model '%s'",
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d - ⚡] Received Batch #%d, %d tool calls (%.2fs, %d tokens)',
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d - →] Received single tool call (%.2fs, %d tokens)',
            '[AI API Call #%d] Sending request with %d tokens',
            '[AI API Call #%d] Completed (%.2fs, %d tokens)',
            '[AI Summary] Total: %.2fs | API calls: %d (%.2fs) | Tools: %d (%.2fs) | Tokens: %d (in: %d, out: %d) | Batches: %d',
        ])
        self.assertEqual([r.msg for r in mock_tool_logger.records if r.levelname == 'DEBUG'], [
            "[AI Tool - Batch #%d ⚡] '%s' with args (%s)",
            "[AI Tool - Batch #%d - %.2fs] Completed '%s'%s",
            "[AI Tool - Batch #%d ⚡] '%s' with args (%s)",
            "[AI Tool - Batch #%d - %.2fs] Completed '%s'%s",
            "[AI Tool →] '%s' with args (%s)",
            "[AI Tool - %.2fs] Completed '%s'%s",
        ])
        self.assertEqual([r.msg for r in mock_service_logger.records if r.levelname == 'DEBUG'], [
            '[AI Tool Summary] Batch #%d completed, %d tool calls',
        ])
