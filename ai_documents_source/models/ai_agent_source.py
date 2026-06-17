from odoo import models, fields
from odoo import _, api


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    document_id = fields.Many2one('documents.document', string="Source Document", index=True)
    type = fields.Selection(
        selection_add=[('document', 'Document')],
        ondelete={'document': lambda recs: recs.write({'type': 'binary'})}
    )

    @api.depends_context('uid')
    @api.depends('document_id', 'visibility', 'create_uid')
    def _compute_user_has_access(self):
        """
        Override to check if the user has access to the document.
        Also enforces visibility restriction for private sources.
        """
        document_sources = self.filtered(lambda s: s.type == 'document')
        for source in document_sources:
            base_access = source.document_id.user_permission != 'none'
            # Apply visibility restriction
            if base_access and source.visibility == 'private':
                base_access = (source.create_uid.id == self.env.user.id) or self.env.is_system()
            source.user_has_access = base_access
        super(AIAgentSource, self - document_sources)._compute_user_has_access()

    def action_access_source(self):
        """
        Override to open the document if document_id exists.
        """
        self.ensure_one()
        if self.document_id:
            return {
            'type': 'ir.actions.act_window',
            'name': _('Source Document'),
            'view_mode': 'kanban',
            'res_model': 'documents.document',
            'domain': [('id', '=', self.document_id.id)],
            'view_id': self.env.ref('documents.document_view_kanban').id,
        }

        return super().action_access_source()
