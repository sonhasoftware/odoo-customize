# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import lxml.html

from odoo import models, api

_logger = logging.getLogger(__name__)


class MailRenderMixinAI(models.AbstractModel):
    _inherit = "mail.render.mixin"

    @api.model
    def _render_template_get_valid_options(self):
        return super()._render_template_get_valid_options() | {"eval_ai_prompts"}

    def _valid_field_parameter(self, field, name):
        return name == "eval_ai_prompts" or super()._valid_field_parameter(field, name)

    @api.model
    def _render_template(self, template_src, model, res_ids, engine='inline_template', add_context=None, options=None):
        result = super()._render_template(
            template_src, model, res_ids,
            engine=engine,
            add_context=add_context,
            options=options,
        )
        if not (options or {}).get("eval_ai_prompts"):
            return result

        # check if there are html with AI prompts to evaluate, short-circuit if not
        has_ai_prompts = False
        for rendered in result.values():
            if rendered and lxml.html.fromstring(rendered).xpath("//div[hasclass('o_editor_prompt')]"):
                has_ai_prompts = True
                break

        if not has_ai_prompts:
            return result

        ai_composer = self.env.ref("ai.ai_mail_template_prompt_evaluator", raise_if_not_found=False)
        if not ai_composer:
            _logger.warning("The AI composer record used to evaluate AI prompts for mails is missing. The prompts are removed.")

        default_agent = self.env.ref("ai.ai_default_agent", raise_if_not_found=False) or self.env["ai.agent"]
        if not default_agent:
            _logger.warning("The default AI agent is missing. The prompts are removed.")

        author = self.env.user.partner_id
        if self and 'author_id' in self and len(self) == 1:
            author = self.author_id

        for res_id in result:
            ai_context = ""
            if ai_composer:
                ai_context += ai_composer.default_prompt or ""
                ai_context += "\n\nUse the following information when necessary to generate the response:\n\n"
                # TODO: How about the recipients list?
                ai_context += f"\nSender: {author.name}"
                # `lang` is already set in the context by _render_field which calls this method.
                ai_context += f"\nRecipient language: {self.env.context.get('lang', 'en_US')}"
            result[res_id] = default_agent._eval_ai_prompts(result[res_id],
                                                            remove_prompts=not (ai_composer and default_agent),
                                                            ai_context=ai_context)

        return result

    def _render_field(self, field, res_ids, engine='inline_template',
                      # lang options
                      compute_lang=False, res_ids_lang=False, set_lang=False,
                      # rendering context and options
                      add_context=None, options=None):
        # Use the field's eval_ai_prompts attr if no 'eval_ai_prompts' option is provided
        if getattr(self._fields[field], "eval_ai_prompts", False) and "eval_ai_prompts" not in (options or {}):
            options = {**(options or {}), 'eval_ai_prompts': True}
        return super()._render_field(
            field, res_ids, engine=engine,
            compute_lang=compute_lang, set_lang=set_lang, res_ids_lang=res_ids_lang,
            add_context=add_context, options=options,
        )
