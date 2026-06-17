# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class BaseAutomation(models.Model):
    _inherit = "base.automation"

    ai_autosort_folder_id = fields.Many2one(
        "documents.document",
        string="Sorted Folder",
        domain=[("type", "=", "folder"), ("shortcut_document_id", "=", False)],
    )

    _sql_constraints = [
        ('unique_ai_autosort_folder_id',
         "UNIQUE(ai_autosort_folder_id)",
         'Only one automation rule can be used to sort with AI a given folder'),
    ]

    def _process(self, records, domain_post=None):
        if (
            self.env.context.get("ai_documents_skip_autosort")
            and records
            and records._name == "documents.document"
            and self.ai_autosort_folder_id
        ):
            return
        return super()._process(records, domain_post)
