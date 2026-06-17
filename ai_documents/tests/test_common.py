from odoo import Command
from odoo.addons.ai_fields.tools import ai_field_insert
from odoo.tests import TransactionCase, Form


class TestAiDocumentsCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_internal = cls.env['res.users'].create({
            'name': 'user_test',
            'login': 'user_test',
            'group_ids': [
                Command.set(cls.env.ref('base.group_user').ids),
            ],
        })
        cls.ir_action_tools_childs = cls.env["ir.actions.server"].create([{
            "model_id": cls.env["ir.model"]._get_id("documents.document"),
            "state": "code",
            "name": "Write Name",
            "code": "record.write({'name': new_name})",
        }, {
            "model_id": cls.env["ir.model"]._get_id("documents.document"),
            "state": "code",
            "name": "Return Count",
            "code": "ai['result'] = 'action return value'",
        }])

        cls.folder, cls.target_folder, cls.other_folder = cls.env['documents.document'].create([{
            'name': 'Folder',
            'type': 'folder',
        }, {
            'name': 'Target Folder',
            'type': 'folder',
        }, {
            'name': 'Other Folder',
            'type': 'folder',
        }])

    def setUp(self):
        super().setUp()

        # Test using both at the same type (to test "multi" type server actions)
        self.ir_action_tool = self.env["ir.actions.server"].create({
            "model_id": self.env["ir.model"]._get_id("documents.document"),
            "state": "multi",
            "name": "Rename and return count",
            "use_in_ai": False,  # Will be forced by the wizard
            "child_ids": self.ir_action_tools_childs.ids,
        })

        # Configure the prompt using the wizard
        Doc = self.env['documents.document']
        sort_wizard = Form(self.env['ai_documents.sort'].with_context(default_folder_id=self.folder.id))
        sort_wizard.ai_sort_prompt = f"Execute the action then move in {Doc._ai_folder_insert(self.target_folder.id)} here is the name {ai_field_insert('name', 'Name')}"
        sort_wizard.ai_tool_ids.add(self.ir_action_tool)
        sort_wizard.save().action_setup_folder()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()

    def tearDown(self):
        super().tearDown()
        self.env['base.automation'].search([('ai_autosort_folder_id', '!=', False)]).unlink()
        self.env['base.automation']._unregister_hook()
        self.env['base.automation']._register_hook()
