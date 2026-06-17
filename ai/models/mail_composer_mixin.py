# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MailComposerMixinAI(models.AbstractModel):
    _inherit = 'mail.composer.mixin'

    body = fields.Html(eval_ai_prompts=True)
