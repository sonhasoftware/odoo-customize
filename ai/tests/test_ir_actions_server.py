import json
from unittest.mock import patch

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger
from odoo.addons.ai.models.ir_actions_server import _logger as tool_logger


@tagged('post_install', '-at_install')
class TestAiServerActions(TransactionCase):
    def _mock_llm_api_get_token(self):
        def _mock_get_api_token(self):
            return "dummy"
        return patch.object(LLMApiService, '_get_api_token', _mock_get_api_token)

    def test_ai_server_action_access(self):
        """Test that the group check is skipped on the tool, but not on the AI action."""
        user = new_test_user(self.env, "internal_user_ai", "base.group_user,base.group_partner_manager")
        partner = self.env["res.partner"].create({"name": "Partner"})

        ir_action_tool = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Write Name",
            "use_in_ai": True,
            "code": "record.write({'name': value})",
            "group_ids": self.env.ref("base.group_system").ids,
        })
        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": ir_action_tool.ids,
                "ai_action_prompt": "Main Prompt",
            },
        )
        llm_calls = 0

        def _mocked_request_llm(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=None,
        ):
            nonlocal llm_calls
            llm_calls += 1
            return ["Done"], [], []

        # Check that we skip the group check on the tools
        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            action.with_user(user).with_context(active_id=partner.id, active_model='res.partner').run()

        self.assertEqual(llm_calls, 1)

        # But not on the AI action
        action.group_ids = self.env.ref("base.group_system").ids
        llm_calls = 0

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm), self.assertRaises(AccessError):
            action.with_user(user).with_context(active_id=partner.id, active_model='res.partner').run()

        self.assertEqual(llm_calls, 0)

    def test_ai_server_action_user_access(self):
        user = new_test_user(self.env, "internal_user_ai", "base.group_user")
        partner = self.env["res.partner"].create({"name": "Partner"})

        # Remove res.partner read access from the user
        access_records = self.env['ir.model.access'].search([
            ('model_id.model', '=', 'res.partner'),
            ('group_id', 'in', user.group_ids.ids)
        ])
        access_records.write({'perm_read': False})

        # Prepare the mocked LLM responses, openai format
        mock_request = self._create_mock_request([
            {
                "output": [
                    {
                        "type": "function_call",
                        "name": "ir_actions_server_search",
                        "call_id": "call_1",
                        "arguments": json.dumps({"model_name": "res.partner", "domain": json.dumps([["id", "=", partner.id]]), "fields": ["name"]}),
                    },
                ],
            },
            {
                "output": [
                    {"text": "Unable to fetch partner details due to access rights."},
                ],
            },
        ])

        # Fetch the ask_ai_agent record with elevated rights, just like they do in the controller
        ask_ai_agent_sudo = self.env["ai.agent"]._get_potential_ask_ai_agent().with_user(user).sudo()

        # Need to ensure the llm model is openai since the mocked request is for openai
        ask_ai_agent_sudo.write({"llm_model": "gpt-4.1"})

        with patch.object(LLMApiService, "_request", mock_request), \
            patch.object(LLMApiService, "_get_api_token", return_value='dummy_token'), \
            self.assertLogs(tool_logger, level='ERROR') as mock_tool_logger:
            ask_ai_agent_sudo._generate_response("test")

        # Single error log stating the user cannot access the records
        error_log_record, = mock_tool_logger.records
        self.assertIn("An error occurred while executing AI: Search: You are not allowed to access 'Contact' (res.partner) records.", error_log_record.msg)

    @mute_logger("odoo.addons.ai.utils.llm_api_service")
    def test_ai_server_action_ai_tool(self):
        llm_calls = 0

        def _mocked_request_llm(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
        ):
            nonlocal llm_calls
            llm_calls += 1
            tool_names = sorted(tools, key=lambda t: tools[t][0])
            self.assertEqual(len(tools or ()), 2)
            self.assertEqual(tool_names[0], f"action_{ir_action_tools[0].id}")
            self.assertEqual(tools[tool_names[0]][0], ir_action_tools[0].name)
            self.assertEqual(tool_names[1], f"action_{ir_action_tools[1].id}")
            self.assertEqual(tools[tool_names[1]][0], ir_action_tools[1].name)
            if llm_calls == 1:
                self.assertFalse(inputs)
                # Call "Return Value" and wait the result
                return self._ai_tool_call(tool_names[0], "call_123456", {})

            if llm_calls == 2:
                self.assertEqual(len(inputs), 2)
                self.assertEqual(inputs[0].get('call_id'), "call_123456")
                self.assertEqual(inputs[1].get('call_id'), "call_123456")
                self.assertEqual(inputs[1].get('output'), "133333337")
                self.assertEqual(inputs[1].get('type'), "function_call_output")
                return self._ai_tool_call(
                    tool_names[1],
                    "call_789123",
                    {"value": "new name", "__end_message": "Renamed!"},
                )

            return [], [], []

        partner = self.env["res.partner"].create({"name": "Partner"})

        ir_action_tools = self.env["ir.actions.server"].create([{
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Return Value",
            "use_in_ai": True,
            "code": "ai['result'] = 133333337",
        }, {
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Write Name",
            "use_in_ai": True,
            "code": "record.write({'name': value})",
        }])

        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": ir_action_tools.ids,
                "ai_action_prompt": "Main Prompt",
            },
        )

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(llm_calls, 2)
        self.assertEqual(partner.name, "new name")

        # Simulate the LLM answering a forbidden action (not in the tools)
        bad_action = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Bad Action",
            "use_in_ai": True,
            "code": "record.write({'name': 'bad'})",
        })

        llm_calls = 0

        def _mocked_request_llm_bad_action(*args, **kwargs):
            nonlocal llm_calls
            llm_calls += 1
            if llm_calls == 1:
                return self._ai_tool_call(f"action_{bad_action.id}", "call_123456", {})
            return [], [], []

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm_bad_action):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(llm_calls, 2)
        self.assertEqual(partner.name, "new name", "Should not execute the action because it's not listed in the tools")

        def _patched_can_execute_action_on_records(*__):
            raise AccessError("")

        with (
            patch.object(self.env.registry['ir.actions.server'], "_can_execute_action_on_records", _patched_can_execute_action_on_records),
            self.assertRaises(AccessError),
        ):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        # Check that if we mark a tool as "not used with AI" we don't send it
        # to the LLM even if the m2m relation still exist
        ir_action_tools[1].use_in_ai = False
        partner.name = 'name'
        llm_calls = 0

        def _mocked_request_llm_use_in_ai_false(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
        ):
            nonlocal llm_calls
            llm_calls += 1
            self.assertEqual(len(tools), 1)
            if llm_calls == 1:
                # The LLM still try to execute it
                return self._ai_tool_call(
                    f"action_{ir_action_tools[1].id}",
                    "call_789123",
                    {"value": "new name"},
                )
            return [], [], []

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm_use_in_ai_false):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(llm_calls, 2)
        self.assertEqual(partner.name, "name", "The action is disabled and should not be executed")

    @mute_logger("odoo.addons.ai.models.ir_actions_server")
    def test_ai_server_action_ai_interactive_tool(self):
        """Check that we raise an error for interactive tools."""
        llm_calls = 0

        def _mocked_request_llm(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
        ):
            nonlocal llm_calls
            llm_calls += 1
            if llm_calls == 1:
                self.assertFalse(inputs)
                return self._ai_tool_call(f"action_{ir_action_tool.id}", "call_123456", {})
            return [], [], []

        partner = self.env["res.partner"].create({"name": "Partner"})

        ir_action_tool = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("res.partner"),
            "state": "code",
            "name": "Return Value",
            "use_in_ai": True,
            # The action tries to open a window action
            "code": """action = {
                "type": "ir.actions.act_window",
                "res_model": "res.partner",
                "target": "new",
            }
            """,
        })

        action = self.env["ir.actions.server"].create(
            {
                "model_id": self.env["ir.model"]._get_id("res.partner"),
                "state": "ai",
                "name": "Test",
                "ai_tool_ids": ir_action_tool.ids,
                "ai_action_prompt": "Main Prompt",
            },
        )

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            action.with_context(active_model=partner._name, active_id=partner.id).run()

        self.assertEqual(llm_calls, 2)
        self.assertIn(
            'This action is interactive and cannot be executed by the agent.',
            ''.join(partner.message_ids.mapped('body')),
            'Should log the error on the partner',
        )

    def _ai_tool_call(self, name, call_id, arguments):
        # Simulate the response of `_request_llm` when the LLM ask to execute a tool
        return [], [(name, call_id, arguments)], [{"call_id": call_id, "name": name, "arguments": json.dumps(arguments)}]

    def _create_mock_request(self, responses):
        call_count = 0

        def mock_request(*args, **kwargs):
            nonlocal call_count
            result = responses[call_count]
            call_count += 1
            return result

        return mock_request
