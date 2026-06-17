# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    ai_document_or_env_company_id = fields.Many2one(
        "res.company",
        string="AI Company",
        compute="_compute_ai_document_or_env_company_id",
    )

    @api.depends("company_id")
    def _compute_ai_document_or_env_company_id(self):
        for document in self:
            document.ai_document_or_env_company_id = document.company_id or self.env.company
