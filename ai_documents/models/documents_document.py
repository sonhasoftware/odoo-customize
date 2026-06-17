# Part of Odoo. See LICENSE file for full copyright and licensing details.

import ast
import datetime
import logging
import lxml.html

from collections.abc import Iterable
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import is_html_empty

from odoo.addons.ai_fields.tools import parse_ai_prompt_values, ai_field_insert

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    AI_DOCUMENTS_CRON_BATCH_SIZE = 10

    ai_sortable = fields.Boolean(
        "AI Sortable",
        compute="_compute_ai_sortable",
        search="_search_ai_sortable",
    )
    ai_sort_prompt = fields.Html(
        string="AI Folder Sort Prompt",
        help="Prompt used to automatically sort files moved in this folder",
        sanitize=True,
        sanitize_output_method="xml",
        groups="base.group_system",
    )
    ai_to_sort = fields.Boolean(
        "AI To Sort",
        help="Flag to mark the files as to be sorted with AI",
    )

    _sql_constraints = [
        ('check_ai_sort_prompt',
         "CHECK(COALESCE(ai_sort_prompt, '') = '' OR (type = 'folder' AND shortcut_document_id IS NULL))",
         'Only folders can be auto-sorted.'),
    ]

    def write(self, vals):
        if "folder_id" in vals:
            # If the user moved the documents, remove the flag
            vals["ai_to_sort"] = False
        return super().write(vals)

    @api.constrains("type", "ai_sort_prompt")
    def _check_ai_sort_prompt(self):
        if any(d.type != "folder" and d.ai_sort_prompt for d in self):
            raise ValidationError(_("The AI Sort Prompt can only be set on folder."))

    @api.depends("shortcut_document_id", "type", "attachment_id")
    def _compute_ai_sortable(self):
        # Only standard files can be sorted
        for document in self:
            document.ai_sortable = (
                not document.shortcut_document_id
                and document.type == "binary"
                and document.attachment_id
            )

    def _search_ai_sortable(self, operator, value):
        if operator != "in" or not isinstance(value, Iterable) or tuple(value) != (True,):
            return NotImplemented

        return [
            ("shortcut_document_id", "=", False),
            ("type", "=", "binary"),
            ("attachment_id", "!=", False),
        ]

    def _pdf_split(self, new_files=None, open_files=None, vals=None):
        """Skip auto-sorting when splitting documents."""
        return super(DocumentsDocument, self.with_context(ai_documents_skip_autosort=True)) \
            ._pdf_split(new_files, open_files, vals)

    def _ai_action_move_in_folder(self, folder_id):
        self.ensure_one()
        folder = self.browse(folder_id)
        if folder.type != "folder":
            raise UserError(_("Cannot move in a non-folder."))

        if not self.ai_sortable:
            raise UserError(_("This document cannot be auto-sorted."))

        if folder == self.folder_id:
            return _('Moved to "%(folder)s".', folder=self._ai_truncate(folder.name))

        # In case the LLM first moved the document by side effect, it should be able
        # to move to a different folder specified in the prompt
        original_folder = self.folder_id
        if (action := self.env.context.get('ai_executed_action')) and isinstance(action, models.BaseModel):
            original_folder = action.ai_autosort_folder_id

        _prompt, _fields, allowed_ids = parse_ai_prompt_values(
            self.env,
            original_folder.ai_sort_prompt,
            "documents.document",
            False,
        )
        if folder.id not in allowed_ids:
            raise UserError(_("This folder isn't specified in the prompt and cannot be used as target."))

        self.folder_id = folder.id
        return _('Moved to "%(folder)s".', folder=self._ai_truncate(folder.name))

    def _ai_action_add_tags(self, tag_names):
        self.ensure_one()
        tags = self.env["documents.tag"].search([('name', 'in', tag_names)])
        if not tags:
            raise UserError(_("Tags not found: %s", tag_names))

        self.tag_ids |= tags
        return _("Tag(s) %s added", ", ".join(tags.mapped("name")))

    @api.model
    def _get_base_server_actions_domain(self):
        """Don't show tools that need arguments to be executed in documents or technical server actions."""
        return expression.AND([
            super()._get_base_server_actions_domain(),
            [('ai_autosort_folder_id', '=', False)],
            expression.OR([
                [('ai_tool_schema', '=', False)],
                [('use_in_ai', '=', False)]
            ])
        ])

    @api.model
    def _get_search_panel_fields(self):
        panel_fields = super()._get_search_panel_fields()
        if self.env.user._is_admin():
            panel_fields.append("ai_sort_prompt")
        return panel_fields

    ##############
    # Mail alias #
    ##############

    def _message_post_after_hook_template_values(self):
        return {
            **super()._message_post_after_hook_template_values(),
            "ai_to_sort": self.ai_to_sort,
        }

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Delay the LLM calls when documents are sent on an alias to not block the incoming email CRON."""
        if custom_values and (folder_id := custom_values.get("folder_id")):
            rule = self.env['base.automation'].sudo().search(
                [('ai_autosort_folder_id', '=', folder_id)])
            if rule:
                cron = self.env.ref(
                    "ai_documents.ir_cron_ai_documents_sort",
                    raise_if_not_found=False,
                )
                if cron:
                    _logger.info("AI Documents: scheduling auto-sorting")
                    custom_values["ai_to_sort"] = True
                    cron._trigger(self.env.cr.now() + datetime.timedelta(minutes=1))
                else:
                    _logger.warning("AI Documents: AI sorting CRON not found")

        return super(DocumentsDocument, self.with_context(ai_documents_skip_autosort=True)) \
            .message_new(msg_dict, custom_values)

    @api.model
    def _cron_ai_sort(self):
        """Sort documents marked to be sorted with AI."""
        cron = self.env.ref(
            "ai_documents.ir_cron_ai_documents_sort",
            raise_if_not_found=False,
        )
        if cron:
            to_sort_count = self.search_count([("ai_to_sort", "=", True)])
            cron._commit_progress(remaining=to_sort_count)
            if not to_sort_count:
                return

        to_sort = self.search(
            [("ai_to_sort", "=", True)],
            order="create_date ASC, id ASC",
            limit=self.AI_DOCUMENTS_CRON_BATCH_SIZE,
        )

        rules = self.env['base.automation'].sudo().search(
            [('ai_autosort_folder_id', 'in', to_sort.folder_id.ids)])
        rules = rules.grouped("ai_autosort_folder_id")

        for document in to_sort:
            document.ai_to_sort = False
            if cron:
                cron._commit_progress(1)
            if not document.ai_sortable:
                continue

            rule = rules.get(document.folder_id)
            if not rule:
                continue
            try:
                rule._process(
                    document,
                    rule.filter_domain and ast.literal_eval(rule.filter_domain),
                )
            except Exception as e:  # noqa: BLE001
                _logger.error("AI Documents: sorting of %s failed: %s", document.id, e)

    #############################
    # Setup AI Tools and Action #
    #############################

    def action_ai_sort(self):
        """Manually trigger the sort action on the given documents."""
        documents = self.filtered(lambda d: d.ai_sortable and d.folder_id.ai_sort_prompt)
        if not documents:
            raise UserError(_("No document suitable for AI sorting."))

        if len(documents) > 50:
            cron = self.env.ref(
                "ai_documents.ir_cron_ai_documents_sort",
                raise_if_not_found=False,
            )
            if cron:
                _logger.info("AI Documents: scheduling auto-sorting")
                documents.ai_to_sort = True
                cron._trigger(self.env.cr.now() + datetime.timedelta(minutes=1))
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "type": "success",
                        "message": _("Auto sorting has been scheduled"),
                        "sticky": False,
                    },
                }

        ai_actions = self.env["ir.actions.server"].search(
            [("ai_autosort_folder_id", "in", documents.folder_id.ids)])
        ai_action_per_folder = ai_actions.grouped('ai_autosort_folder_id')

        for document in documents:
            ai_action = ai_action_per_folder.get(document.folder_id)
            if not ai_action:
                continue

            document.ai_to_sort = False  # In case we sort a document sent by email
            ai_action._ai_action_run(document)

    def _ai_setup_sort_actions(self, ai_tool_ids=()):
        self.ensure_one()

        # In case we only have the records, we need a parent div to be able to remove it
        content = lxml.html.fromstring(f"<div>{self.ai_sort_prompt or ''}</div>")
        for el in content.xpath('//*[@data-ai-record-id]'):
            el.drop_tree()
        is_prompt_empty = is_html_empty(lxml.html.tostring(content).decode())

        automation_rule = self.env["base.automation"].search(
            [("ai_autosort_folder_id", "=", self.id)],
            limit=1,
        )
        ir_action = self.env["ir.actions.server"].search(
            [("ai_autosort_folder_id", "=", self.id)],
            limit=1,
        )

        if is_prompt_empty:
            automation_rule.unlink()
            ir_action.unlink()
            return

        ir_actions_tools = self.env["ir.actions.server"].browse(ai_tool_ids)
        ir_actions_tools.use_in_ai = True

        action_values = {
            "name": _("Auto-sort documents in %s", self.name),
            "ai_autosort_folder_id": self.id,
            "ai_tool_ids": ir_actions_tools.ids or False,
            "model_id": self.env.ref("documents.model_documents_document").id,
            "state": "ai",
            "ai_action_prompt": Markup("""
                <p>
                    %s
                </p>
                <br/>
            """)
            % _(
                """Here is a document called %(document_name)s and whose content is %(content)s and tags are %(tags)s. The mimetype of the document is %(mimetype)s.""",
                document_name=ai_field_insert("name", _("Name")),
                content=ai_field_insert("attachment_id", _("Document Content")),
                tags=ai_field_insert("tag_ids.name", _("Tags > Name")),
                mimetype=ai_field_insert("mimetype", _("Mimetype")),
            ),
        }
        if ir_action:
            ir_action.write(action_values)
        else:
            ir_action = self.env["ir.actions.server"].create(action_values)

        automation_values = {
            "name": _("Auto-sort documents in %s", self.name),
            "ai_autosort_folder_id": self.id,
            "filter_domain": repr([("folder_id", "=", self.id), ("ai_sortable", "=", True)]),
            "model_id": self.env.ref("documents.model_documents_document").id,
            "trigger": "on_create_or_write",
            "trigger_field_ids": self.env.ref("documents.field_documents_document__folder_id").ids,
            "action_server_ids": ir_action.ids,
        }
        if automation_rule:
            automation_rule.write(automation_values)
        else:
            self.env["base.automation"].create(automation_values)

    def _ai_folder_insert(self, folder_id):
        return Markup('<span data-ai-record-id="%i"/>') % folder_id

    def _ai_format_records(self):
        """Return the information about the folder to insert in the prompt."""
        # Fetch all ancestors in batch
        ancestors = "/".join(self.mapped('parent_path')).split("/")
        ancestors = self.env['documents.document'].browse([int(i) for i in ancestors if i])
        ancestors_names = {str(a.id): self._ai_truncate(a.name).replace(">", "-") for a in ancestors}

        return {
            folder.id: {
                'name': self._ai_truncate(folder.name),
                'path': ' > '.join(ancestors_names[i] for i in folder.parent_path.split("/") if i),
                'company': folder.company_id.name,
                'owner_user': {'id': folder.owner_id.id, 'name': folder.owner_id.name},
            } for folder in self
        }
