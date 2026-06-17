# Part of Odoo. See LICENSE file for full copyright and licensing details.
import json
import logging
import re
from lxml import html

from odoo import api, models
from odoo.exceptions import UserError
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class WebsitePage(models.Model):
    _name = 'website.page'
    _inherit = ['website.page']

    @api.model
    def _extract_snippets_from_template(self, sectionsArch, template_id):
        """
        Get the snippets for a given template.
        :param sectionsArch: The HTML string of the template
        :type sectionsArch: str
        :param template_id: The ID of the template to use to get the English version
        :type template_id: str
        :return: Dictionary mapping snippet IDs to their sections and translated sections
        :rtype: dict
        """
        View = self.env['ir.ui.view']
        snippets_dict = {}
        doc = html.fromstring('<div id="wrap">' + sectionsArch + '</div>')

        # the template_html_en is already wrapped in a div with id="wrap"
        sectionsArch_en = View.with_context(inherit_branding=False, lang='en_US')._render_template(template_id)
        doc_en = html.fromstring(sectionsArch_en)
        # Get the main sections of the template (each is a snippet)
        snippet_sections = doc.xpath('//div[@id="wrap"]/section')
        snippet_sections_en = doc_en.xpath('//div[@id="wrap"]/section')

        # Create a mapping of snippet IDs to English elements for lookup
        en_snippets_map = {}
        for idx, el_en in enumerate(snippet_sections_en):
            snippet_key = el_en.attrib['data-snippet']
            # Because the templates are generated from specific
            # t-snippet-calls such as:
            # "website.new_page_template_about_0_s_text_block",
            # the generated data-snippet looks like:
            # "new_page_template_about_0_s_text_block"
            # while it should be "s_text_block" only.
            if '_s_' in snippet_key:
                el_en.attrib['data-snippet'] = f's_{snippet_key.split("_s_")[-1]}'
            snippet_key = el_en.attrib['data-snippet']
            if snippet_key:
                en_snippets_map[f'{snippet_key}_{idx}'] = html.tostring(el_en, encoding='unicode', method='html')

        # Process each snippet element
        for idx, el in enumerate(snippet_sections):
            snippet_id = el.get('data-snippet')
            if snippet_id:
                # Get the section content (current language)
                section_content = html.tostring(el, encoding='unicode', method='html')
                # Get the translated section content (English)
                translated_section_content = en_snippets_map.get(f'{snippet_id}_{idx}', section_content)
                snippets_dict[f'{snippet_id}_{idx}'] = {
                    'section': section_content,
                    'translated_section': translated_section_content
                }
        return snippets_dict

    @api.model
    def _get_default_cta_configuration(self):
        return {
            'cta_btn_text': 'Contact Us',
            'cta_btn_href': '/contactus'
        }

    def _generate_response(self, content_context, placeholders):
        """
        Generate a response from the AI agent
        :param content_context: The context information for the agent
        :type content_context: str
        :param placeholders: List of placeholder texts to be replaced by AI
        :type placeholders: list
        :return: Response from the AI agent containing generated content
        :rtype: dict
        """
        agent = self.env.ref('ai_website.website_page_generator_agent')
        batch = {str(i + 1): placeholder for i, placeholder in enumerate(placeholders)}
        prompt = json.dumps(batch, ensure_ascii=False)
        try:
            response = agent.get_direct_response(prompt, content_context)
            if len(response) > 0 and isinstance(response[0], str):
                response_dict = json.loads(response[0])
                result = {}
                for i, placeholder in enumerate(placeholders):
                    key = str(i + 1)
                    result[placeholder] = response_dict.get(key, "").strip() or placeholder
                return result
            else:
                return {}
        except (UserError, RequestException) as e:
            return {"error": str(e)}

    @api.model
    def _generate_ai_website_page_html(self, template_id, sectionsArch, content_context):
        """
        Generate the AI-generated HTML content string of the page's template
        :param template_id: The ID of the template to use
        :type template_id: str
        :param content_context: The context information for the agent
        :type content_context: str
        :return: The HTML string of the generated page
        :rtype: str
        """
        website = self.env['website'].get_current_website()
        text_generation_target_lang = website.default_lang_id.code
        text_must_be_translated_for_openai = not text_generation_target_lang.startswith('en_')
        IrQweb = self.env['ir.qweb'].with_context(
            website_id=website.id,
            lang=website.default_lang_id.code
        )
        html_text_processor = self.env['website.html.text.processor']._with_processing_context(
            IrQweb=IrQweb,
            text_generation_target_lang=text_generation_target_lang,
            text_must_be_translated_for_openai=text_must_be_translated_for_openai,
            cta_data=self._get_default_cta_configuration(),
        )
        snippets = self._extract_snippets_from_template(sectionsArch, template_id)
        html_text_processor, generated_content, _dummy = html_text_processor._get_rendered_snippets_content(snippets)
        placeholders = list(generated_content.keys())
        content_context += f" Lang: {text_generation_target_lang}"
        response = self._generate_response(content_context, placeholders)

        if response.get("error"):
            raise UserError(response.get("error"))

        name_replace_parser = re.compile(r"XXXX", re.MULTILINE)
        for key in generated_content:
            if response.get(key):
                generated_content[key] = (name_replace_parser.sub(website.name, response[key], 0))

        result = []
        for key, snippet in snippets.items():
            # The key is like: "s_text_block_0" where the last part _0 is the
            # section index. We want to get the snippet key without the index
            snippet_key = key.rsplit('_', 1)[0]
            el = html_text_processor._update_snippet_content(generated_content, snippet_key, snippet_html=snippet['section'])
            if el is not None:
                el.attrib['data-snippet'] = snippet_key
                result.append(html.tostring(el, encoding='unicode', method='html'))

        ai_html_string = '\n'.join(result)
        return ai_html_string
