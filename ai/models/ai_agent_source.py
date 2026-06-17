# Part of Odoo. See LICENSE file for full copyright and licensing details.
import requests

from odoo import _, api, fields, models
from odoo.addons.mail.tools import link_preview
from odoo.exceptions import AccessError

from ..utils.html_extractor import HTMLExtractor


class AIAgentSource(models.Model):
    _name = 'ai.agent.source'
    _description = 'AI Agent Source'
    _order = 'name'

    name = fields.Char(string="Name")
    agent_id = fields.Many2one('ai.agent', string="Agent", index=True, required=True)
    type = fields.Selection([('url', 'URL'), ('binary', 'File')],
                    default='binary', string='Type', required=True, readonly=True)

    status = fields.Selection(string="Status", selection=[('processing', 'Processing'), ('indexed', 'Indexed'), ('failed', 'Failed')], default='processing')
    is_active = fields.Boolean(string="Active", help="If the source is active, it will be used in the RAG context.")
    error_details = fields.Text(string="Error Details", readonly=True)

    attachment_id = fields.Many2one('ir.attachment', string="Attachment", index=True, ondelete='cascade')
    mimetype = fields.Char(related='attachment_id.mimetype')
    file_size = fields.Integer(related='attachment_id.file_size')

    url = fields.Char(string="URL")

    user_has_access = fields.Boolean(compute="_compute_user_has_access", readonly=True)
    visibility = fields.Selection([
        ('public', 'Công khai'),
        ('private', 'Riêng tư')
    ], string="Quyền riêng tư", default='public', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        sources = super().create(vals_list)
        trigger_embeddings_cron = False
        trigger_scrape_urls_cron = False
        for source in sources:
            if source.attachment_id:
                source.attachment_id.write({
                    'res_model': 'ai.agent.source',
                    'res_id': source.id,
                })
            if source.type == 'binary' and source.status == 'processing':
                trigger_embeddings_cron = True
            elif source.type == 'url':
                trigger_scrape_urls_cron = True

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()
            try:
                self.env['ai.embedding']._cron_generate_embedding(batch_size=100)
            except Exception:
                pass
        if trigger_scrape_urls_cron:
            self.env.ref('ai.ir_cron_process_sources')._trigger()
            try:
                self.env['ai.agent.source']._cron_process_sources()
                self.env['ai.embedding']._cron_generate_embedding(batch_size=100)
            except Exception:
                pass

        return sources

    @api.model
    def create_from_attachments(self, attachment_ids, agent_id):
        """
        Create AI agent sources from existing attachments.

        :param attachment_ids: list of attachment IDs
        :type attachment_ids: list of int
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        attachments = self.env['ir.attachment'].browse(attachment_ids)
        checksums = attachments.mapped('checksum')
        agent = self.env['ai.agent'].browse(agent_id)
        embedding_model = agent._get_embedding_model()
        existing_checksums = set(
            self.env['ai.embedding'].search([('checksum', 'in', checksums), ('embedding_model', '=', embedding_model)]).mapped('checksum')
        )
        # Filter attachments that already have embeddings using their checksum
        matching_attachments = attachments.filtered(lambda a: a.checksum in existing_checksums)

        vals_list = []
        for attachment in attachments:
            source = {
                'name': attachment.name,
                'agent_id': agent_id,
                'attachment_id': attachment.id,
                'type': 'binary',
            }
            if attachment in matching_attachments:
                source['status'] = 'indexed'
                source['is_active'] = True

            vals_list.append(source)

        return self.create(vals_list)

    @api.model
    def create_from_binary_files(self, files_datas, agent_id):
        """
        Create AI agent sources from binary records.
        :param records: list of records with name and datas
        :type records: list of dicts
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        attachment_ids = self.env['ir.attachment'].create(files_datas).ids
        return self.create_from_attachments(attachment_ids, agent_id)

    @api.model
    def create_from_urls(self, urls, agent_id):
        """
        Create AI agent sources from URLs.

        :param urls: list of urls
        :type urls: list of str
        :param agent_id: agent id
        :type agent_id: int
        :return: list of created AI agent sources
        :rtype: list of ai.agent.source records
        """
        if not urls:
            return self.browse()

        if not self.env.is_system():
            raise AccessError(_('Only administrators can create sources from URLs.'))

        request_session = requests.Session()
        vals_list = []
        for url in urls:
            preview = link_preview.get_link_preview_from_url(url, request_session)
            if preview and preview.get('og_title'):
                name = preview['og_title']
            else:
                name = url
            url_source = {
                'name': name,
                'url': url,
                'agent_id': agent_id,
                'type': 'url',
            }
            vals_list.append(url_source)

        return self.create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_attachments(self):
        """Delete attachments when a source is deleted."""
        for source in self:
            if source.attachment_id:
                source.attachment_id.unlink()

    @api.depends_context('uid')
    @api.depends('attachment_id', 'visibility', 'create_uid')
    def _compute_user_has_access(self):
        """
        Compute user access by delegating to the underlying source.
        Overriden in ai_documents and ai_knowledge.
        If visibility is 'private', only the creator or system admin can access.
        """
        for source in self:
            if source.type == 'url':
                base_access = True
            elif source.type == 'binary':
                base_access = self.env.user._is_internal()
            else:
                base_access = self.env.user._is_internal()

            # Apply visibility restriction
            if base_access and source.visibility == 'private':
                base_access = (source.create_uid.id == self.env.user.id) or self.env.is_system()

            source.user_has_access = base_access

    def _get_source_embeddings_status(self, embedding_model):
        """
        Get the current embedding status for a source with the given model.

        :param embedding_model: embedding model
        :type embedding_model: str
        :return: dict with status info
        :rtype: dict
        """
        self.ensure_one()

        # Get all embeddings for this source
        checksum = self.attachment_id.checksum
        embedding_chunks = self.env['ai.embedding'].search([
            ('checksum', '=', checksum),
            ('embedding_model', '=', embedding_model)
        ])

        if not embedding_chunks:
            return {'has_chunks': False}

        failed_count = embedding_chunks.filtered('has_embedding_generation_failed')
        missing_vectors = embedding_chunks.filtered(lambda e: not e.embedding_vector)

        return {
            'has_chunks': True,
            'has_failed': bool(failed_count),
            'has_missing': bool(missing_vectors),
        }

    def _update_source_status(self, embedding_model):
        """
        Update source status based on current embedding state.

        :param embedding_model: embedding model
        :type embedding_model: str
        :return: True if source status was updated, False otherwise
        :rtype: bool
        """
        self.ensure_one()
        embedding_info = self._get_source_embeddings_status(embedding_model)

        if not embedding_info['has_chunks']:
            # No chunks exist, it needs to be processed first
            return False

        elif embedding_info.get('has_failed'):
            self.write({
                'status': 'failed',
                'is_active': False,
                'error_details': _("Embedding generation failed using the current LLM model selected."),
            })

        elif embedding_info.get('has_missing'):
            self.write({
                'status': 'processing',
                'is_active': False,
                'error_details': False,
            })

        else:
            # Has chunks and no missing vectors, it's ready to be used
            self.write({
                'status': 'indexed',
                'is_active': True,
                'error_details': False,
            })

        return True

    def _sync_new_agent_provider(self, embedding_model):
        """
        Sync sources when embedding model changes.

        :param embedding_model: embedding model
        :type embedding_model: str
        """
        sources_to_process = self.env[self._name]
        for source in self:
            can_update = source._update_source_status(embedding_model)
            # If the source can't be updated and it has an attachment, it means it has no chunks,
            # so we need to process it first
            if not can_update and source.attachment_id:
                source.write({
                    'status': 'processing',
                    'is_active': False,
                    'error_details': False,
                })
                sources_to_process |= source

        if sources_to_process:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()
            try:
                self.env['ai.embedding']._cron_generate_embedding(batch_size=100)
            except Exception:
                pass

    def action_retry_failed_source(self):
        """
        Retry failed sources by deleting the source chunks and re-triggering the appropriate cron job.
        """
        self.ensure_one()
        if self.status == 'failed':
            source_chunks = self.env['ai.embedding'].search([('checksum', '=', self.attachment_id.checksum), ('embedding_model', '=', self.agent_id._get_embedding_model())])
            if source_chunks:
                source_chunks.unlink()

            if self.url:
                cron = 'ai.ir_cron_process_sources'
            elif self.attachment_id:
                cron = 'ai.ir_cron_generate_embedding'
            else:
                cron = False

            if cron:
                self.write({
                    'status': 'processing',
                    'is_active': False,
                    'error_details': False,
                })

                self.env.ref(cron)._trigger()
                try:
                    if cron == 'ai.ir_cron_process_sources':
                        self.env['ai.agent.source']._cron_process_sources()
                        self.env['ai.embedding']._cron_generate_embedding(batch_size=100)
                    elif cron == 'ai.ir_cron_generate_embedding':
                        self.env['ai.embedding']._cron_generate_embedding(batch_size=100)
                except Exception:
                    pass

    def action_open_sources_dialog(self):
        """
        Open the add sources dialog.
        """
        agent_id = self.env.context.get('agent_id')
        return {
            "type": "ir.actions.client",
            "tag": "ai_open_sources_dialog",
            "params": {
                "agent_id": agent_id,
            }
        }

    def action_access_source(self):
        """
        Access the source content. Overriden in ai_documents and ai_knowledge.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': self.url or f'/web/content/{self.attachment_id.id}?download=true',
            'target': 'new',
        }

    def _cron_process_sources(self):
        """
        Process sources for content extraction and create attachments if needed.
        Overriden in ai_knowledge
        """
        sources_with_urls = self.env['ai.agent.source'].search([('type', '=', 'url'), ('status', '=', 'processing')])
        extractor = HTMLExtractor()
        trigger_embeddings_cron = False
        for source in sources_with_urls:
            result = extractor.scrap(source.url)
            if not result or not result['content']:
                error_message = result.get('error', _("URL content cannot be extracted."))
                source.write({
                    'status': 'failed',
                    'error_details': error_message,
                })
                continue

            trigger_embeddings_cron |= self._process_source_content(source, result['content'])

        if trigger_embeddings_cron:
            self.env.ref('ai.ir_cron_generate_embedding')._trigger()

    def _process_source_content(self, source, content, url=None):
        """
        Process source content and create attachment if needed.
        :param source: source record
        :param content: content of the source
        :param url: url of the source
        :return: True if the source was processed successfully
        and needs to be indexed, False otherwise
        """
        embedding_model = source.agent_id._get_embedding_model()
        attachment_url = url or source.url

        existing_attachment = self.env['ir.attachment'].search([('url', '=', attachment_url)], limit=1)

        if existing_attachment:
            new_attachment = existing_attachment.copy()
            new_attachment.write({
                'res_model': 'ai.agent.source',
                'res_id': source.id,
            })
            source.attachment_id = new_attachment.id
            # Check if embeddings already exist
            if not self.env['ai.embedding'].search_count([('checksum', '=', new_attachment.checksum), ('embedding_model', '=', embedding_model)], limit=1):
                return True
            else:
                source.write({
                    'status': 'indexed',
                    'is_active': True,
                })
                return False
        else:
            # Create new attachment
            attachment_name = f"{source.name}-({attachment_url})"
            new_attachment = self.env['ir.attachment'].create({
                'name': attachment_name,
                'res_model': 'ai.agent.source',
                'res_id': source.id,
                'raw': content,
                'mimetype': 'text/html',
                'url': attachment_url,
                'index_content': content,
            })
            source.attachment_id = new_attachment.id
            return True
