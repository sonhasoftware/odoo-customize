import logging
import werkzeug.exceptions

from odoo import http
from odoo.http import request
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AIWebsiteController(http.Controller):

    @http.route(['/ai_website/generate_page'], type='jsonrpc', auth='user', website=True)
    def generate_website_page_content(self, instructions, name, sectionsArch, tone, templateId, **post):
        """Generate website content using the AI agent with text-only processing."""
        if not request.env.user.has_group('website.group_website_restricted_editor'):
            raise werkzeug.exceptions.Forbidden()

        context = f"""- Page name: {name} - Instructions: {instructions} - Tone: {tone}"""
        try:
            ai_generated_html = request.env['website.page']._generate_ai_website_page_html(templateId, sectionsArch, context, **post)
            result = {'html': ai_generated_html}
        except UserError as e:
            _logger.error("Error generating website page content: %s", e)
            result = {'error': str(e), 'html': sectionsArch}

        return result
