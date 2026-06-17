# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailTemplateAI(models.Model):
    _inherit = 'mail.template'

    body_html = fields.Html(eval_ai_prompts=True)

    def _check_can_be_rendered(self, fnames=None, render_options=None):
        """Override to ensure that the prompts are not evaluated during checks."""
        render_options = {**(render_options or {}), 'eval_ai_prompts': False}
        return super()._check_can_be_rendered(fnames=fnames, render_options=render_options)
