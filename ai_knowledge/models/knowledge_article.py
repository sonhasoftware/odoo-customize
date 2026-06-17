from odoo import api, models


class KnowledgeArticle(models.Model):
    _inherit = 'knowledge.article'

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources when an article is deleted."""
        source_linked_to_article = self.env['ai.agent.source'].search([('article_id', 'in', self.ids)])
        if source_linked_to_article:
            source_linked_to_article.unlink()
