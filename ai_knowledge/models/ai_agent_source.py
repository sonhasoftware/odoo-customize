from odoo import api, models, fields

from odoo.addons.ai.utils.html_extractor import HTMLExtractor


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _inherit = ['ai.agent.source']

    article_id = fields.Many2one('knowledge.article', string="Source Article")
    type = fields.Selection(
        selection_add=[('knowledge_article', 'Knowledge Article')],
        ondelete={'knowledge_article': lambda recs: recs.write({'type': 'binary'})}
    )

    @api.model
    def create_from_articles(self, article_ids, agent_id):
        """Create AI agent sources from articles."""
        vals_list = []
        articles = self.env['knowledge.article'].browse(article_ids)
        for article in articles:
            vals_list.append({
                'name': article.name,
                'agent_id': agent_id,
                'article_id': article.id,
                'type': 'knowledge_article',
            })
        sources = super().create(vals_list)
        if sources:
            self.env.ref('ai.ir_cron_process_sources')._trigger()

    @api.depends_context('uid')
    @api.depends('article_id', 'visibility', 'create_uid')
    def _compute_user_has_access(self):
        """
        Override to check if the user has access to the article.
        Also enforces visibility restriction for private sources.
        """
        article_sources = self.filtered(lambda s: s.type == 'knowledge_article')
        for source in article_sources:
            base_access = source.article_id.user_has_access
            # Apply visibility restriction
            if base_access and source.visibility == 'private':
                base_access = (source.create_uid.id == self.env.user.id) or self.env.is_system()
            source.user_has_access = base_access
        super(AIAgentSource, self - article_sources)._compute_user_has_access()

    def action_access_source(self):
        """Override to open the article if article_id exists"""
        self.ensure_one()
        if self.article_id:
            article_url = self.article_id.article_url
            if article_url:
                return {
                    'type': 'ir.actions.act_url',
                    'url': article_url,
                    'target': 'new',
                }
        return super().action_access_source()

    def _cron_process_sources(self):
        """
        Extended method to handle both URL scraping and knowledge article processing.
        """
        article_sources = self.search([('type', '=', 'knowledge_article'), ('status', '=', 'processing')])
        extractor = HTMLExtractor()
        trigger_embeddings_cron = False

        for source in article_sources:
            parent_article = source.article_id
            article_descendants = parent_article._get_descendants()
            all_articles = article_descendants | parent_article
            index_content = ""
            for article in all_articles:
                result = extractor.extract_from_html(article.body)
                if result['content']:
                    index_content += result['content'] + '\n'

            article_url = parent_article.article_url
            should_trigger = self._process_source_content(source, index_content, url=article_url)
            if should_trigger:
                trigger_embeddings_cron = True

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

        super()._cron_process_sources()
