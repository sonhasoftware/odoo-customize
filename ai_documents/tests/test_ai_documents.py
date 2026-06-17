import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import Form
from odoo.tools import mute_logger

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai_documents.tests.test_common import TestAiDocumentsCommon


class TestAiDocuments(TestAiDocumentsCommon):
    def test_ai_documents_access(self):
        """Test that only an admin can change the prompt of a folder."""
        with self.assertRaises(AccessError):
            self.env['documents.document'].with_user(self.user_internal).create({'ai_sort_prompt': 'test', 'type': 'folder'})

        folder = self.env['documents.document'].with_user(self.user_internal).sudo().create({'ai_sort_prompt': 'test', 'type': 'folder'}).sudo(False)

        with self.assertRaises(AccessError):
            folder.ai_sort_prompt = 'test 2'

    @mute_logger("odoo.addons.ai.utils.llm_api_service", "odoo.addons.ai.models.ir_actions_server", "odoo.addons.ai_documents.models.ir_actions_server")
    def test_ai_documents_sort(self):
        """Test the "Auto-sort" flow using tools."""
        Doc = self.env['documents.document']
        llm_calls = 0

        # Check that we write the prompt on the source folder
        self.assertIn('data-ai-record-id', self.folder.ai_sort_prompt)
        self.assertIn(str(self.target_folder.id), self.folder.ai_sort_prompt)
        self.assertIn('data-ai-field="name"', self.folder.ai_sort_prompt)
        self.assertFalse(self.target_folder.ai_sort_prompt)

        automation_rule = self.env["base.automation"].search([("ai_autosort_folder_id", "=", self.folder.id)])
        self.assertEqual(len(automation_rule), 1)
        self.assertEqual(len(automation_rule.action_server_ids), 1)

        # Should create an action of type `ai`, that will render the `ai_sort_prompt` of the source folder
        self.assertEqual(automation_rule.action_server_ids.state, "ai")
        self.assertEqual(automation_rule.filter_domain, repr([("folder_id", "=", self.folder.id), ("ai_sortable", "=", True)]))
        self.assertEqual(automation_rule.trigger, "on_create_or_write")
        self.assertIn("Here is a document called ", automation_rule.action_server_ids.ai_action_prompt)
        ai_tool_ids = automation_rule.action_server_ids.ai_tool_ids
        self.assertEqual(len(ai_tool_ids), 2, "Should have the `multi` type action, and the `move in folder` action.")

        # That `ai` action has the tools we set on the wizard
        move_in_folder = self.env.ref("ai_documents.ir_actions_server_move_in_folder")
        self.assertEqual(self.ir_action_tool | move_in_folder, ai_tool_ids)
        self.assertTrue(all(ai_tool_ids.mapped("use_in_ai")))

        llm_target_folder = self.target_folder

        def _mocked_request_llm(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False
        ):
            nonlocal llm_calls
            llm_calls += 1
            tool_names = sorted(tools, key=lambda t: tools[t][0])
            self.assertIn("Here is a document called", "".join(user_prompts))
            self.assertIn("Execute the action then move", "".join(user_prompts))
            self.assertIn("Document Name", "".join(user_prompts))

            self.assertEqual(len(tools or ()), 2)
            self.assertEqual(tool_names[0], "ir_actions_server_move_in_folder")
            self.assertEqual(tools[tool_names[0]][0], move_in_folder.ai_tool_description)
            self.assertEqual(tool_names[1], f"action_{self.ir_action_tool.id}")
            self.assertEqual(tools[tool_names[1]][0], self.ir_action_tool.name)

            if llm_calls == 1:
                self.assertFalse(inputs)
                return self._ai_tool_call(
                    f"action_{self.ir_action_tool.id}",
                    "call_123456",
                    {'new_name': 'new name'},
                )

            if llm_calls == 2:
                self.assertEqual(len(inputs), 2)
                self.assertEqual(inputs[0].get('call_id'), "call_123456")
                self.assertEqual(inputs[0].get('name'), f"action_{self.ir_action_tool.id}")
                self.assertEqual(inputs[1].get('call_id'), "call_123456")
                self.assertEqual(inputs[1].get('output'), "action return value")
                self.assertEqual(inputs[1].get('type'), "function_call_output")
                return self._ai_tool_call(
                    "ir_actions_server_move_in_folder",
                    "call_789123",
                    {'folder_id': llm_target_folder.id},
                )

            return [], [], []

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "Document Name",
                "type": "binary",
                "datas": "VGVzdCBmaWxl",
            })

        self.assertTrue(document.ai_sortable)
        self.assertTrue(Doc.search([("id", "=", document.id), ("ai_sortable", "=", True)]))
        self.assertEqual(llm_calls, 3)
        self.assertEqual(document.name, "new name")
        self.assertEqual(document.folder_id, self.target_folder)

        # Check that we don't try to auto-sort non-sortable document
        llm_calls = 0

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "folder",
            })

        self.assertEqual(llm_calls, 0)

        # Try to create a loop between 2 folders (if the target folder is also "Sort With AI")

        def _mocked_request_llm_loop(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
        ):
            nonlocal llm_calls
            llm_calls += 1
            if llm_calls % 2 == 1:
                target = self.folder if "Target folder prompt" in str(user_prompts) else self.target_folder
                return self._ai_tool_call(
                    "ir_actions_server_move_in_folder",
                    "call_789123",
                    {'folder_id': target.id},
                )
            return [], [], []

        sort_wizard = Form(self.env['ai_documents.sort'].with_context(default_folder_id=self.target_folder.id))
        sort_wizard.ai_sort_prompt = f"Target folder prompt: move in {Doc._ai_folder_insert(self.folder.id)}"
        sort_wizard.ai_tool_ids.add(self.ir_action_tool)
        sort_wizard.save().action_setup_folder()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm_loop):
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "binary",
                "datas": "VGVzdCBmaWxl",
            })

        self.assertTrue(document.ai_sortable)
        self.assertTrue(Doc.search([("id", "=", document.id), ("ai_sortable", "=", True)]))
        self.assertEqual(llm_calls, 4, "All automation rules can be executed once")
        self.assertEqual(document.folder_id, self.folder)
        self.assertEqual(document.name, "test")

        # Re-test the exact same flow, but this time the LLM return a folder not in the prompt for some reason
        llm_calls = 0
        llm_target_folder = self.other_folder

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm):
            doc = Doc.create({
                "folder_id": self.folder.id,
                "name": "Document Name",
                "type": "binary",
                "datas": "VGVzdCBmaWxl",
            })

        self.assertEqual(doc.folder_id, self.folder, "Silently ignore the error")
        self.assertIn(
            "This folder isn't specified in the prompt and cannot be used as target.",
            "".join(doc.message_ids.mapped("body")),
            "Should log the error on the document",
        )
        self.assertEqual(llm_calls, 3)

        # Test that removing the prompt delete the automation rule
        # (we only left inserted records without instruction)
        self.env['ai_documents.sort'].create({
            'folder_id': self.folder.id,
            'ai_sort_prompt': Doc._ai_folder_insert(self.target_folder.id),
            'ai_tool_ids': self.ir_action_tool.ids,
        }).action_setup_folder()
        self.assertFalse(automation_rule.exists())
        self.assertFalse(automation_rule.action_server_ids.exists())

        shortcut = document.action_create_shortcut()
        self.assertFalse(shortcut.ai_sortable)
        self.assertFalse(Doc.search([("id", "=", shortcut.id), ("ai_sortable", "=", True)]))

        # Test the case where the LLM will execute a tool that will move the documents,
        # with any tools, and then try to move it with the "AI Move Document" tool (the second
        # folder won't have a prompt, and so it should take the folder linked to the action
        # and not to the document).
        llm_calls = 0

        def _mocked_request_llm_move(
            service, llm_model, system_prompts, user_prompts, tools=None,
            files=None, schema=None, temperature=0.2, inputs=(), web_grounding=False,
        ):
            nonlocal llm_calls
            llm_calls += 1
            if llm_calls == 1:
                return self._ai_tool_call(
                    f"action_{ir_action_tool_first_move.id}",
                    "call_abcdef",
                    {},
                )
            if llm_calls == 2:
                return self._ai_tool_call(
                    "ir_actions_server_move_in_folder",
                    "call_789123",
                    {'folder_id': self.target_folder.id},
                )
            return [], [], []

        ir_action_tool_first_move = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("documents.document"),
            "state": "code",
            "name": "Move",
            "code": "record.write({'folder_id': %i})" % self.other_folder.id,
        })

        sort_wizard = Form(self.env['ai_documents.sort'].with_context(default_folder_id=self.folder.id))
        sort_wizard.ai_sort_prompt = f"Target folder prompt: move in {Doc._ai_folder_insert(self.target_folder.id)}"
        sort_wizard.ai_tool_ids.add(self.ir_action_tool)
        sort_wizard.ai_tool_ids.add(ir_action_tool_first_move)
        sort_wizard.save().action_setup_folder()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()

        with patch.object(LLMApiService, "_request_llm", _mocked_request_llm_move):
            document = Doc.create({
                "folder_id": self.folder.id,
                "name": "test",
                "type": "binary",
                "datas": "VGVzdCBmaWxl",
            })

        self.assertEqual(llm_calls, 3)
        self.assertEqual(document.folder_id, self.target_folder)

    def _ai_tool_call(self, name, call_id, arguments):
        # Simulate the response of `_request_llm` when the LLM ask to execute a tool
        return [], [(name, call_id, arguments)], [{"call_id": call_id, "name": name, "arguments": json.dumps(arguments)}]
