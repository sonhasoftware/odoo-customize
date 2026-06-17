# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    @api.model
    def create_ai_agent_sources_from_documents(self, document_ids, agent_id):
        """
        Create AI agent sources from documents.
        """
        documents = self.browse(document_ids)
        # Create copies of the attachments
        attachment_ids = []
        document_source_mapping = {}
        for document in documents:
            attachment = document.attachment_id.with_context(no_document=True).copy({
                "res_model": False,
                "res_id": False,
            })
            attachment_ids.append(attachment.id)
            document_source_mapping[attachment.id] = document.id
        sources = self.env['ai.agent.source'].create_from_attachments(attachment_ids, agent_id)
        for source in sources:
            source.write({
                'type': 'document',
                'document_id': document_source_mapping[source.attachment_id.id]
            })
        return sources

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources when a document is deleted."""
        source_linked_to_document = self.env['ai.agent.source'].search([('document_id', 'in', self.ids)])
        if source_linked_to_document:
            source_linked_to_document.unlink()
