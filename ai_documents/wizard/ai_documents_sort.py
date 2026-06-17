# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, Command, api, fields, models
from odoo.tools import is_html_empty


class AiDocumentsSort(models.TransientModel):
    """Wizard responsible to create the Automation Rule and the server action to auto sort files."""

    _name = "ai_documents.sort"
    _description = "Ai Documents Sort"

    @api.model
    def default_get(self, fields):
        values = super().default_get(fields)

        tool_actions = self.env["ir.actions.server"]
        if "folder_id" in values and "ai_tool_ids" in fields:
            existing_ir_action = self.env["ir.actions.server"].search(
                [("ai_autosort_folder_id", "=", values["folder_id"])],
                limit=1,
            )
            if existing_ir_action:
                # The folder is auto-sorted
                values["ai_sort_prompt"] = self.env["documents.document"].browse(values["folder_id"]).ai_sort_prompt
                values["ai_tool_ids"] = [Command.set(existing_ir_action.ai_tool_ids.ids)]
                return values

            # By default, add all pinned action that can be used as AI tools
            folder = self.env["documents.document"].browse(values["folder_id"])
            tool_actions = self._get_folder_actions(folder)

        if "ai_tool_ids" in fields:
            move_in_folder = self.env.ref(
                "ai_documents.ir_actions_server_move_in_folder",
                raise_if_not_found=False,
            )
            if move_in_folder:
                tool_actions |= move_in_folder
            values["ai_tool_ids"] = [Command.set(tool_actions.ids)]

        finance_folder = self.env.ref("documents.document_finance_folder", raise_if_not_found=False)
        if "ai_sort_prompt" not in fields or not finance_folder:
            return values

        values["ai_sort_prompt"] = _(
            "If the document is an invoice, send it to %s",
            self.env["documents.document"]._ai_folder_insert(finance_folder.id),
        )

        return values

    folder_id = fields.Many2one(
        "documents.document",
        string="Folder",
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
        required=True,
    )
    ai_sort_prompt = fields.Html(string="AI Folder Sort Prompt")

    ai_tool_ids = fields.Many2many(
        "ir.actions.server",
        string="Additional Tools",
        domain="[('id', 'in', allowed_tools_ids)]",
    )

    allowed_tools_ids = fields.Many2many(
        "ir.actions.server",
        string="Allowed Tools",
        compute="_compute_allowed_tools_ids",
    )

    # UI fields
    model = fields.Char(compute="_compute_ui_fields")
    relation = fields.Char(compute="_compute_ui_fields")
    is_ai_sort_prompt_set = fields.Boolean("Is Prompt Set", compute="_compute_is_prompt_set")

    def _compute_ui_fields(self):
        # Because the widget is generic for all models / fields
        # we simply create "UI" field instead of overwriting the widget
        self.model = "documents.document"
        self.relation = "documents.document"

    @api.depends("ai_sort_prompt")
    def _compute_is_prompt_set(self):
        for record in self:
            record.is_ai_sort_prompt_set = not is_html_empty(record.folder_id.ai_sort_prompt)

    @api.depends("folder_id")
    def _compute_allowed_tools_ids(self):
        documents_tools = self.env["ir.actions.server"].search([
            ("model_id.model", "=", "documents.document"),
            ("usage", "in", ["documents_embedded", "ir_actions_server"]),
        ])
        documents_tools = documents_tools.filtered(lambda d: d.ai_tool_is_candidate)
        self.allowed_tools_ids = documents_tools

    def action_setup_folder(self):
        self.folder_id.ai_sort_prompt = self.ai_sort_prompt
        self.folder_id._ai_setup_sort_actions(self.ai_tool_ids.ids)

    def action_delete(self):
        self.folder_id.ai_sort_prompt = False
        self.folder_id._ai_setup_sort_actions(self.ai_tool_ids.ids)

    def _get_folder_actions(self, folder):
        """Return the actions that can be turned into AI tools."""
        embedded_server_actions = (
            self.env["documents.document"]
            ._get_folder_embedded_actions(folder.ids)
            .get(folder.id)
        )
        if not embedded_server_actions:
            return self.env["ir.actions.server"]

        tool_actions = embedded_server_actions.action_id.filtered(lambda a: a.type == "ir.actions.server")
        # Convert the `ir.actions.actions` to `ir.actions.server`
        # (those models share the same ids index, see `base/data/base_data.sql`)
        tool_actions = self.env["ir.actions.server"].browse(tool_actions.ids)
        return tool_actions.filtered("ai_tool_is_candidate").filtered("use_in_ai")
