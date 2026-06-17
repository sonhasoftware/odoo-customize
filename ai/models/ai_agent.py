# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import logging
import json
import lxml.html

from ast import literal_eval
from collections import defaultdict
from datetime import datetime, timedelta
from lxml import etree
from textwrap import dedent
try:
    from markdown2 import markdown
except ImportError:
    markdown = None

from odoo import _, api, Command, fields, models
from odoo.osv import expression
from odoo.exceptions import UserError, ValidationError
from odoo.tools import file_open, html_sanitize, SQL, is_html_empty, ormcache
from odoo.http import request
from odoo.tools.mail import html_to_inner_content
from odoo.tools.misc import mute_logger, submap

from odoo.addons.ai.utils.llm_api_service import LLMApiService
from odoo.addons.ai.utils.llm_providers import PROVIDERS, get_provider

_logger = logging.getLogger(__name__)


TEMPERATURE_MAP = {
    'analytical': 0.2,
    'balanced': 0.5,
    'creative': 0.8,
}

# Pre-prompts are put in a dictionary so that they can easily be overridden
PREPROMPTS = {
    'default_system_prompt': "You are a RAG assistant.",
    'tools': dedent("""
        You have access to tools that can perform actions. Only use these tools when:
        1. The user explicitly requests the action.
        2. The action is clearly the most appropriate response to their query.

        If the user asks you to perform an action, retrieve the required information from his prompt and the conversation history, then use the tool.

        If date is needed, Use today's date to make a relative date if the user didn't provide a clear one (e.g. tomorrow, in one week, etc.).
        Rarely suggest the actions in your response.
    """).strip(),
    'restrict_to_sources': dedent("""
        ## INSTRUCTIONS FOR ANSWERING QUERIES

        1. For greetings (hello, hi, how are you), reply with a greeting.

        2. For all other questions, you MUST ONLY use information from the provided context and conversation history.

        3. If the context and history don't contain information to answer the query:
           - use the assistant/user messages as context or ask the user to provide more information.
           - DO NOT make up information or use your general knowledge.

        4. When answering based on the context:
           - Synthesize information from multiple sources when appropriate
           - Consider the conversation history for follow-up questions

        5. If a user asks a follow-up question like 'what is this?' or 'tell me more', refer to the conversation history to understand the context and answer accordingly.

        6. If no context is provided at all, respond with: 'No source information has been provided for me to reference.'

        7. Avoid using HTML elements in your response.
    """).strip(),
    'context': dedent("""
        - Use the context to answer the question.
    """).strip(),
    'unaccessible_references': dedent("""
        - Ignore UNACCESSIBLE_REFERENCES in the response's references even if you use them in your response.
        - Append only accessible references to the response's references if you use them, if you don't use any in the response or only unaccessible ones, don't append any references.
    """).strip(),
}


def compute_report_measures(fields, field_attrs=None, active_measures=None, sum_aggregator_only=False):
    """
    Python equivalent of the JavaScript computeReportMeasures function.

    Args:
        fields (dict): Dictionary of field definitions from fields_get()
        field_attrs (dict): Dictionary of field attributes with visibility info
        active_measures (list): List of active measure field names
        sum_aggregator_only (bool): Only include fields with 'sum' aggregator

    Returns:
        dict: Ordered dictionary of measures with their field definitions
    """
    if field_attrs is None:
        field_attrs = {}
    if active_measures is None:
        active_measures = []

    # Start with the count measure
    measures = {"__count": {"name": "__count", "string": "Count", "type": "integer"}}

    # Process regular fields
    for field_name, field in fields.items():
        if field_name == "id":
            continue

        # Check if field is invisible
        field_attr = field_attrs.get(field_name, {})
        if field_attr.get("isInvisible", False):
            continue

        # Check if field is numeric and has aggregator
        if field.get("type") in ["integer", "float", "monetary"]:
            aggregator = field.get("aggregator")
            if aggregator:
                if sum_aggregator_only and aggregator != "sum":
                    continue
                # Filter field to only include the keys we want
                filtered_field = submap(field, ["type", "aggregator", "name", "string", "sortable"])
                measures[field_name] = filtered_field

    # Add active measures to the measure list
    # This is rarely necessary, but can be useful for functional fields
    # with overridden read_group methods
    for measure in active_measures:
        if measure not in measures and measure in fields:
            # Filter field to only include the keys we want
            filtered_field = submap(fields[measure], ["type", "aggregator", "name", "string", "sortable"])
            measures[measure] = filtered_field

    # Override field strings from field_attrs if provided
    for field_name, field_attr in field_attrs.items():
        if field_attr.get("string") and field_name in measures:
            measures[field_name] = dict(measures[field_name])
            measures[field_name]["string"] = field_attr["string"]

    # Sort measures: Count is always last, others alphabetically by string
    def sort_key(item):
        field_name, field_def = item
        if field_name == "__count":
            return 1, ""  # Count goes last
        return 0, field_def.get("string", "").lower()

    sorted_measures = sorted(measures.items(), key=sort_key)
    return dict(sorted_measures)


def clean_search_view_xml(search_view_arch):
    """Clean and restructure search view XML for AI consumption."""
    if not search_view_arch:
        return ""

    # Parse XML
    tree = etree.fromstring(search_view_arch)

    # Create new clean structure
    clean_tree = etree.Element("search")

    # 1. Add searchable fields (excluding only those with invisible="1")
    searchable_fields_elem = etree.SubElement(clean_tree, "searchable_fields")
    for field in tree.xpath(".//field[@name and not(@invisible='1') and not(ancestor::group)]"):
        # Copy only essential attributes
        clean_field = etree.SubElement(searchable_fields_elem, "field")
        for attr in ["name", "string", "filter_domain", "operator"]:
            if field.get(attr):
                clean_field.set(attr, field.get(attr))

    # 2. Add filters grouped by separators (excluding those with invisible="1")
    filters_elem = etree.SubElement(clean_tree, "filters")

    # Process filters in groups separated by separators
    current_group = None
    for elem in tree:
        if elem.tag == "separator":
            # Start a new group on separator
            current_group = None
        elif elem.tag == "filter" and elem.get("name") and elem.get("invisible") != "1":
            # Skip filters that are inside <group> elements (those are groupbys)
            if elem.getparent().tag != "group":
                if current_group is None:
                    current_group = etree.SubElement(filters_elem, "group")
                clean_filter = etree.SubElement(current_group, "filter")
                for attr in ["name", "string", "domain", "date"]:
                    if elem.get(attr):
                        clean_filter.set(attr, elem.get(attr))

    # 3. Add groupby filters with extracted field information
    groupbys_elem = etree.SubElement(clean_tree, "groupbys")
    for group in tree.xpath(".//group"):
        for filter_elem in group.xpath(".//filter[@name and not(@invisible='1')]"):
            if filter_elem.get("context") and "group_by" in filter_elem.get("context"):
                clean_filter = etree.SubElement(groupbys_elem, "filter")
                clean_filter.set("name", filter_elem.get("name"))
                if filter_elem.get("string"):
                    clean_filter.set("string", filter_elem.get("string"))

                # Extract the actual field name from the context
                context_str = filter_elem.get("context")
                context_dict = literal_eval(context_str)
                if "group_by" in context_dict:
                    clean_filter.set("group_by_field", context_dict["group_by"])

    # Return compact XML string
    return etree.tostring(clean_tree, encoding="unicode", pretty_print=False)


def validate_groupbys(model, groupbys):
    if not groupbys:
        return

    model_fields = model.fields_get()
    invalid_groupbys = []
    for groupby in groupbys:
        if len(groupby.split(".")) > 1 or not model_fields.get(groupby, {}).get('groupable'):
            invalid_groupbys.append(groupby)

    if invalid_groupbys:
        raise ValueError(f"The following groupby values are not allowed: {invalid_groupbys}")


def validate_search_terms(search_terms):
    if not search_terms:
        return

    invalid_search_terms = []
    for search_term in search_terms:
        field, __ = search_term.split("=")
        if len(field.split(".")) > 1:
            invalid_search_terms.append(search_term)

    if invalid_search_terms:
        raise ValueError(f"Search terms with field chains are not allowed: {invalid_search_terms}")


class AIAgent(models.Model):
    _name = 'ai.agent'
    _description = "AI Agent"
    _order = 'name'

    @api.model
    def _get_llm_model_selection(self):
        selection = []
        for provider in PROVIDERS:
            selection.extend(provider.llms)
        return selection

    active = fields.Boolean(default=True)
    name = fields.Char(string="Agent Name", related='partner_id.name', required=True, readonly=False)
    subtitle = fields.Char(string="Description")
    system_prompt = fields.Text(string="System Prompt", help="Customize to control relevance and formatting.")
    response_style = fields.Selection(
        selection=[
            ('analytical', "Analytical"),
            ('balanced', "Balanced"),
            ('creative', "Creative"),
        ],
        string="Response Style",
        default='balanced',
        required=True,
    )

    llm_model = fields.Selection(
        selection=_get_llm_model_selection,
        string="LLM Model",
        default='gpt-4o',
        required=True,
    )
    restrict_to_sources = fields.Boolean(
        string="Restrict to Sources",
        help="If checked, the agent will only respond based on the provided sources.")
    image_128 = fields.Image("Image", related="partner_id.image_1920", max_width=128, max_height=128, readonly=False)
    avatar_128 = fields.Image("Avatar", related="partner_id.avatar_128")
    topic_ids = fields.Many2many(
        'ai.topic',
        string="Topics",
        help="A topic includes instructions and tools that guide Odoo AI in helping the user complete their tasks.",
    )
    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)

    is_system_agent = fields.Boolean('System Agent', default=False)

    sources_ids = fields.One2many(
        'ai.agent.source',
        'agent_id',
        string="Sources",
    )
    sources_fully_processed = fields.Boolean(compute="_compute_sources_fully_processed", default=True)
    is_ask_ai_agent = fields.Boolean(
        'Is Natural Language Query Agent',
        compute='_compute_is_ask_ai_agent',
        search='_search_is_ask_ai_agent'
    )

    @api.model_create_multi
    def create(self, vals_list):
        with file_open('ai/static/description/icon.png', 'rb') as f:
            image_placeholder = f.read()
        for vals in vals_list:
            partner = self.env['res.partner'].create({
                'name': vals.get('name'),
                'active': False,
            })
            vals['partner_id'] = partner.id
        ai_agents = super().create(vals_list)
        for agent in ai_agents:
            if not agent.image_128:
                agent.image_128 = base64.b64encode(image_placeholder)
        return ai_agents

    def write(self, vals):
        if 'partner_id' in vals:
            raise ValidationError(_("The partner linked to an AI agent can't be changed"))

        old_providers = {agent.id: agent._get_provider() for agent in self}
        result = super().write(vals)
        for agent in self:
            new_provider = agent._get_provider()
            if new_provider != old_providers[agent.id]:
                embedding_model = agent._get_embedding_model()
                agent.sources_ids._sync_new_agent_provider(embedding_model)
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_sources(self):
        """Delete sources (and their attachments) when an agent is deleted."""
        for agent in self:
            if agent.sources_ids:
                agent.sources_ids.unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_system_agent(self):
        """Prevent deletion of system agents."""
        system_agents = self.filtered('is_system_agent')
        if system_agents:
            raise UserError(_("System agents cannot be deleted."))

    def copy_data(self, default=None):
        default = dict(default or {})
        vals_list = super().copy_data(default=default)
        if 'name' not in default:
            for agent, vals in zip(self, vals_list):
                vals['name'] = _("%s (copy)", agent.name)
        return vals_list

    def _get_provider(self):
        self.ensure_one()
        return get_provider(self.env, self.llm_model)

    def _get_embedding_model(self):
        self.ensure_one()
        provider = self._get_provider()
        for p in PROVIDERS:
            if p.name == provider:
                return p.embedding_model
        raise UserError(_("No embedding model found for the selected provider"))

    def action_refresh_sources(self):
        """
        Refresh the sources to show the new status if any was changed by the cron.
        Run the cron if there are sources to process.
        """
        self.ensure_one()
        cron = self.env.ref('ai.ir_cron_generate_embedding')
        unprocessed_sources = self.sources_ids.filtered(lambda s: s.status == 'processing')
        if unprocessed_sources:
            cron._trigger()

        return {
            'type': 'ir.actions.client',
            'tag': 'soft_reload',
        }

    def get_direct_response(self, prompt: str, context_message: str = "", enable_html_response: bool = False):
        """Get a direct response from the agent's provider LLM without chat history or channel creation."""
        self.ensure_one()
        response = self._generate_response(prompt=prompt, extra_system_context=context_message)
        if enable_html_response and markdown:
            for i, message in enumerate(response):
                raw_html = markdown(message, extras=['fenced-code-blocks', 'tables', 'strike'])
                response[i] = html_sanitize(raw_html)
        return response

    def _generate_response_for_channel(self, mail_message, channel):
        self.ensure_one()

        prompt, session_info_context = self._parse_user_message(mail_message)
        response = self.with_context(discuss_channel=channel)._generate_response(
            prompt=prompt,
            chat_history=[{'content': session_info_context, 'role': 'user'}] + self._retrieve_chat_history(channel),
            extra_system_context=self._build_extra_system_context(channel),
        )
        for message in response or []:
            self._post_ai_response(channel, message)

    def _post_error_message(self, error_message: str, channel):
        self.ensure_one()
        try:
            response = self._generate_response(
                prompt=f"Error '{error_message}' occured. Generate a message for the user stating that we are unable to process the request but don't mention any technical details. Perhaps also tell them to try again later.",
                chat_history=self._retrieve_chat_history(channel),
                extra_system_context="Do not mention any technical terms, links, or error codes in the generated message.")
            for message in response or []:
                self._post_ai_response(channel, message)
        except Exception:
            # Fallback if the LLM itself is down or failing
            fallback_msg = _("Xin lỗi, tôi đang gặp sự cố kết nối với hệ thống AI. Chi tiết lỗi: %s", error_message)
            self._post_ai_response(channel, fallback_msg)

    def open_agent_chat(self):
        self.ensure_one()
        channel = self._get_or_create_ai_chat()
        return {
            'type': 'ir.actions.client',
            'tag': 'agent_chat_action',
            'params': {
                'channelId': channel.id,
            },
        }

    def close_chat(self, channel_id: int):
        self.ensure_one()
        channel = self.env['discuss.channel'].search([
            ('id', '=', channel_id),
            ('is_member', '=', True),
            ('channel_type', '=', 'ai_chat')
        ])
        if channel:
            channel.sudo().unlink()

    @api.model
    def action_ask_ai(self, user_prompt: str):
        ask_ai_agent = self._get_potential_ask_ai_agent()
        if not ask_ai_agent:
            raise UserError(_('No configured Ask AI agent. Please contact your administrator.'))

        channel = ask_ai_agent._get_or_create_ai_chat()
        return {
            'type': 'ir.actions.client',
            'tag': 'agent_chat_action',
            'params': {
                'channelId': channel.id,
                'user_prompt': user_prompt,
            },
        }

    @api.model
    def get_ask_ai_agent(self):
        agent = self._get_potential_ask_ai_agent()
        return agent.read(['id', 'name'])[0] if agent else None

    @api.model
    def _get_potential_ask_ai_agent(self):
        agents = self.search([('is_ask_ai_agent', '=', True)])
        if not agents:
            return None

        agents = sorted(agents, key=lambda a: len(a.topic_ids))
        return agents[0]

    @api.model
    def _get_ask_ai_topics(self):
        return [t for t in (
            self.env.ref('ai.ai_topic_natural_language_query', raise_if_not_found=False),
            self.env.ref('ai.ai_topic_information_retrieval_query', raise_if_not_found=False)
        ) if t]

    def _compute_is_ask_ai_agent(self):
        ask_ai_topics = self._get_ask_ai_topics()
        for agent in self:
            agent.is_ask_ai_agent = bool(set(agent.topic_ids) & set(ask_ai_topics))

    def _search_is_ask_ai_agent(self, operator, value):
        if operator not in ('=', '!='):
            raise UserError(_("Invalid search operator."))

        if ask_ai_topics := self._get_ask_ai_topics():
            if operator == '=' and value or operator == '!=' and not value:  # truthy
                return [("topic_ids", "in", [t.id for t in ask_ai_topics])]
            elif operator == '=' and not value or operator == '!=' and value:  # falsy
                return [("topic_ids", "not in", [t.id for t in ask_ai_topics])]
        else:
            return [('id', '=', False)]

    def _post_ai_response(self, channel, message):
        formatted_message = message
        if markdown:
            raw_html = markdown(message, extras=['fenced-code-blocks', 'tables', 'strike'])
            formatted_message = html_sanitize(raw_html)
        else:
            formatted_message = html_sanitize(message)
        channel.sudo().message_post(
            author_id=self.partner_id.id,
            body=formatted_message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )

    def _generate_response(self, prompt, chat_history=None, extra_system_context=""):
        """Generate an AI response for the given user prompt.

        This method orchestrates the complete response generation flow:
        1. Constructs system context from agent settings and additional context
        2. Retrieves relevant RAG context from sources (if any)
        3. Sends the complete conversation to the LLM API
        4. Processes any tool calls in the response, executing them and continuing the conversation
        5. Stops when the LLM provides a final response or all tools request termination

        :param prompt: The user's input prompt
        :param chat_history: Previous conversation messages to include as context
        :param extra_system_context: Additional system instructions to include
        :return: List of response messages from the LLM and/or tool termination messages
        :raises UserError: If no LLM provider is found for the selected model
        """
        self.ensure_one()
        _logger.debug("[AI Prompt] %s", prompt)
        system_messages = self._build_system_context(extra_system_context=extra_system_context)

        similar_embeddings = self.env['ai.embedding']
        referenced_attachments = []

        if self.sources_ids:
            try:
                provider = self._get_provider()
                embedding_model = self._get_embedding_model()
                response = LLMApiService(env=self.env, provider=provider).get_embedding(
                    input=prompt,
                    dimensions=self.env['ai.embedding']._get_dimensions(),
                    model=embedding_model
                )
                if response and "data" in response:
                    prompt_embedding = response['data'][0]['embedding']
                    similar_embeddings = self.env['ai.embedding']._get_similar_chunks(
                        query_embedding=prompt_embedding,
                        sources=self.sources_ids,
                        embedding_model=self._get_embedding_model(),
                        top_n=5
                    )
                    if similar_embeddings:
                        ref_names = set()
                        for embedding in similar_embeddings:
                            if embedding.attachment_id and embedding.attachment_id.name:
                                ref_names.add(embedding.attachment_id.name)
                        referenced_sources = self.env['ai.agent.source'].search([('attachment_id.name', 'in', list(ref_names))])
                        accessible_sources = referenced_sources.filtered(lambda s: s.user_has_access)
                        referenced_attachments = accessible_sources.mapped('name')
            except Exception as e:
                _logger.warning("Failed to retrieve similar embeddings: %s", e)

        rag_context = self._build_rag_context(prompt, similar_embeddings=similar_embeddings)
        if rag_context:
            system_messages.extend(rag_context)

        response_list = LLMApiService(env=self.env, provider=self._get_provider()).request_llm(
            self.llm_model,
            system_messages,
            [],
            inputs=(chat_history or []) + [{'role': 'user', 'content': prompt}],
            tools=self.topic_ids.tool_ids._get_ai_tools(),
            temperature=TEMPERATURE_MAP[self.response_style],
        )

        if referenced_attachments and response_list:
            # Find the index of the last string in response_list to append the citation only once
            last_str_idx = -1
            for i in range(len(response_list) - 1, -1, -1):
                if isinstance(response_list[i], str):
                    last_str_idx = i
                    break
            
            if last_str_idx != -1:
                resp = response_list[last_str_idx]
                if not any(ref.lower() in resp.lower() for ref in referenced_attachments) and "tài liệu tham khảo" not in resp.lower() and "references" not in resp.lower():
                    ref_list = "\n\n---\n**Tài liệu tham khảo:**\n" + "\n".join(f"- {name}" for name in referenced_attachments)
                    response_list = list(response_list)
                    response_list[last_str_idx] = resp + ref_list

        return response_list

    def _retrieve_chat_history(self, discuss_channel, no_messages=20):
        chat_history = [
            {
                'content': message.body,
                # sudo() => public users can access author_id (res.partner) to check whether it is an ai agent.
                'role': 'assistant' if message.sudo().author_id.agent_ids else 'user',
            }
            for message in discuss_channel.message_ids[1 : no_messages + 1]
        ]

        chat_history.reverse()
        return chat_history

    def _build_system_context(self, extra_system_context: str = ""):
        self.ensure_one()
        system_content = self.system_prompt or "You are a RAG assistant."
        system_content += f"\n\nToday's date to be used: {fields.Datetime.now()} (UTC)"
        if not self.env.user._is_public():
            partner_vals, _ = self.env.user.partner_id._ai_read(['name', 'function', 'email', 'phone'], None)
            system_content += f"\n\nUser info: {partner_vals}"
        system_content += f"\nAll record data timestamps are in UTC. In responses, convert them to {(self.env.context.get('tz') or self.env.user.tz or 'UTC')}"

        if self.topic_ids:
            system_content += PREPROMPTS['tools']

        messages = [system_content]

        if self.topic_ids:
            topic_instructions = "\n\n".join(
                [topic.instructions for topic in self.topic_ids if topic.instructions])
            if topic_instructions:
                messages.append(f"Additional topic instructions:\n{topic_instructions}.")

        if self.restrict_to_sources:
            messages.append(PREPROMPTS['restrict_to_sources'])

        if isinstance(extra_system_context, str):
            messages.append(extra_system_context)
        elif isinstance(extra_system_context, list):
            messages += extra_system_context

        return messages

    def _build_rag_context(self, prompt, similar_embeddings=None):
        self.ensure_one()
        messages = []
        context = ""
        if self.sources_ids:
            if similar_embeddings is None:
                provider = self._get_provider()
                embedding_model = self._get_embedding_model()
                response = LLMApiService(env=self.env, provider=provider).get_embedding(
                    input=prompt,
                    dimensions=self.env['ai.embedding']._get_dimensions(),
                    model=embedding_model
                )
                if not response or "data" not in response:
                    raise UserError(_("Failed to get embeddings for the prompt."))

                prompt_embedding = response['data'][0]['embedding']
                similar_embeddings = self.env['ai.embedding']._get_similar_chunks(
                    query_embedding=prompt_embedding,
                    sources=self.sources_ids,
                    embedding_model=self._get_embedding_model(),
                    top_n=5
                )
            if similar_embeddings:
                referenced_attachments = set()
                for embedding in similar_embeddings:
                    context += f"{embedding.attachment_id.name}\n{embedding.content}\n\n"
                    if embedding.attachment_id and embedding.attachment_id.name:
                        referenced_attachments.add(embedding.attachment_id.name)
                referenced_sources = self.env['ai.agent.source'].search([('attachment_id.name', 'in', list(referenced_attachments))])
                unaccessible_sources_names = referenced_sources.filtered(lambda s: not s.user_has_access).mapped('name')
                accessible_referenced_sources_names = referenced_sources.filtered(lambda s: s.user_has_access).mapped('name')
                context += f"##References:\n{', '.join(accessible_referenced_sources_names)}"
                if unaccessible_sources_names:
                    context += f"\n [UNACCESSIBLE_REFERENCES: {', '.join(unaccessible_sources_names)}] {PREPROMPTS['unaccessible_references']}"
        if context:
            messages.append(f"##Context information:\n\n{context}\n{PREPROMPTS['context']}")
        return messages

    @api.depends("sources_ids.status")
    def _compute_sources_fully_processed(self):
        for record in self:
            record.sources_fully_processed = not record.sources_ids.filtered(lambda s: s.status == 'processing')

    def _eval_ai_prompts(self, rendered_html, remove_prompts=False, ai_context=""):
        """Evaluate AI prompts in the given HTML content"""
        if is_html_empty(rendered_html):
            return rendered_html

        Wrapper = rendered_html.__class__
        root = lxml.html.fromstring(rendered_html)

        prompt_containers = root.xpath("//div[hasclass('o_editor_prompt')]")

        if not prompt_containers:
            return Wrapper(rendered_html)

        for container in prompt_containers:
            prompt_content_elements = container.xpath(
                ".//div[hasclass('o_editor_prompt_content')]"
            )

            if remove_prompts:
                container.getparent().remove(container)
                continue

            if not prompt_content_elements:
                container.getparent().remove(container)
                continue

            assert (
                len(prompt_content_elements) == 1
            ), "There should be only one prompt content element inside a prompt container."
            prompt_text = prompt_content_elements[0].text_content().strip()

            if not prompt_text:
                container.getparent().remove(container)
                continue

            response = self._generate_response(prompt_text, extra_system_context=ai_context)

            if not response:
                container.getparent().remove(container)
                continue

            # Wrapped each line of the response in a <p> tag.
            wrapped_content = "\n".join(f"<p>{content}</p>" for content in response[0].split("\n") if content.strip())
            replacement_html_str = html_sanitize(wrapped_content, sanitize_attributes=True, sanitize_style=True)
            container.getparent().replace(container, lxml.html.fromstring(replacement_html_str))

        return Wrapper(lxml.html.tostring(root, encoding="unicode", method="html"))

    def _get_or_create_ai_chat(self, channel_name=None):
        channel = self._get_ai_chat_channel()
        if not channel:
            channel = self._create_ai_chat_channel(channel_name)
        return channel

    def _get_ai_chat_channel(self):
        channels = self.env['discuss.channel'].search([
            ('is_member', '=', True),
            ('channel_type', '=', 'ai_chat'),
        ], order='id desc')
        return channels.filtered(lambda channel: channel.sudo().ai_agent_id == self)[:1]

    def _create_ai_chat_channel(self, channel_name=None):
        # The method is called in three safe scenarios:
        # - Testing: An admin is creating a channel (from the test button in the AI app) to test an AI agent's configuration.
        # - Internal Features: An internal user is creating a channel for features like `ai_composer`.
        # - Public Access: A public/portal user is creating a channel (through livechat for example).
        #   The access to the agent is verified by the `_is_user_access_allowed` method.
        # In all cases, the channel is created between the AI agent and the current user, so using sudo() for channel creation is safe.

        guest = self.env["mail.guest"]._get_guest_from_context()
        with mute_logger("odoo.sql_db"):
            self.env.cr.execute(SQL(
                "SELECT pg_advisory_xact_lock(%s, %s) NOWAIT;",
                guest.id if self.env.user._is_public() else self.env.user.partner_id.id,
                self.id
            ))

        channel = self.env['discuss.channel'].sudo().create({
            "ai_agent_id": self.id,
            "channel_member_ids": [
                Command.create({"guest_id": guest.id} if self.env.user._is_public() else {"partner_id": self.env.user.partner_id.id}),
                Command.create({"partner_id": self.partner_id.id}),
            ],
            "channel_type": "ai_chat",
            # sudo() => visitor can set the name of the channel
            "name": channel_name if channel_name else self.partner_id.sudo().name,
        })
        return channel

    def _facets_to_xml(self, facets):
        """Convert facets JSON array to simplified XML elements format with reduced nesting."""
        if not facets:
            return ""

        xml_parts = []
        for facet in facets:
            facet_attrs = []

            for key, value in facet.items():
                if value:
                    if key == "values" and isinstance(value, list):
                        values_str = "|".join(str(v) for v in value)
                        facet_attrs.append(f'{key}="{values_str}"')
                    else:
                        facet_attrs.append(f'{key}="{value}"')

            if facet_attrs:
                xml_parts.append(f'<facet {" ".join(facet_attrs)}/>')

        return "\n    ".join(xml_parts)

    def _parse_user_message(self, mail_message):
        self.ensure_one()
        session_info_context = ""
        if self.is_ask_ai_agent:
            context_lines = []
            context_lines.append("<session_info_context>")
            context_lines.append(
                f'  <user id="{self.env.user.id}" name="{self.env.user.display_name}" model="res.users"/>'
            )
            context_lines.append(
                f'  <partner id="{self.env.user.partner_id.id}" name="{self.env.user.partner_id.name}" model="res.partner"/>'
            )
            context_lines.append(
                f'  <company id="{self.env.company.id}" name="{self.env.company.name}" model="res.company"/>'
            )

            user_context = dict(self.env['res.users'].context_get())
            if user_context.get("tz"):
                context_lines.append(
                    f'    <timezone value="{user_context["tz"]}"/>'
                )

            # Current view as a single element if present
            if current_view_info := self.env.context.get("current_view_info"):
                action_id = current_view_info.get("action_id")
                action = self.env['ir.actions.actions'].browse(action_id)
                current_action_name = None
                if action.type == 'ir.actions.act_window':
                    current_action = self.env['ir.actions.act_window'].browse(action_id)
                elif action.type == 'ir.actions.server':
                    current_action = self.env['ir.actions.server'].browse(action_id)
                elif action.type == 'ir.actions.client':
                    current_action = self.env['ir.actions.client'].browse(action_id)
                if current_action:
                    current_action_name = current_action.name

                context_lines.append(
                    f'  <current_view id="{current_view_info.get("view_id")}" '
                    f'model="{current_view_info.get("model")}" '
                    f'type="{current_view_info.get("view_type")}" '
                    f'action_id="{action_id}" '
                    f'action="{current_action_name}" '
                    f'available_view_types="{current_view_info.get("available_view_types")}"/>'
                )

                facets = current_view_info.get("facets", [])
                if facets:
                    context_lines.append(f'  <active_search_facets>\n    {self._facets_to_xml(facets)}\n  </active_search_facets>')

                search_view = self.env[current_action.res_model].get_view(current_action.search_view_id.id, 'search')
                search_view_xml = clean_search_view_xml(search_view['arch']) if search_view else ""
                if search_view_xml:
                    context_lines.append(f"  {search_view_xml}")

            context_lines.append("</session_info_context>")
            session_info_context = "\n".join(context_lines) + "\n" + dedent("""
                The above provides information about the current user and where in the app he is at.
                <session_info_context> contains important information about the the user. partner element is the linked res.partner record to the user.
                It may also contain info about the <current_view> that I'm in in the UI.
                <active_search_facets>, if exists, contains the currently active facets in the shown search bar in the UI.
                <search> is the specification of the search bar in the UI. It contains the blueprint of the things that can be done to it by the user. Information from it can be useful when calling terminating tool calls.
                Knowing <current_view>, <active_search_facets>, and/or <search> provides you a rough idea of where the user is and what he's looking at.
            """.strip())
        return html_to_inner_content(mail_message.body), session_info_context

    @api.model
    def _parse_domain(self, model_name, domain_json_str: str | None):
        if not domain_json_str or not domain_json_str.strip():
            return None

        try:
            domain_array = json.loads(domain_json_str)
            expression.normalize_domain(domain_array)
            return domain_array
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for custom domain: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid custom domain for model '{model_name}': {e}")

    def _build_extra_system_context(self, discuss_channel):
        """Build extra system context based on the agent's configuration."""
        self.ensure_one()
        extra_context = []
        topic_xml_ids = self.topic_ids.get_external_id().values()
        if any(topic in ["ai.ai_topic_natural_language_query", "ai.ai_topic_information_retrieval_query"] for topic in topic_xml_ids):
            extra_context.append(self._get_available_models())
        if self.get_external_id()[self.id] == "ai.ai_agent_natural_language_search":
            extra_context.append(self._get_available_menus())
            extra_context.append(self._get_date_calculation_reference())
        elif env_context := discuss_channel.ai_env_context:  # if channel has ai related context (e.g. draft flow) pass it to the agent's extra context
            extra_context += env_context

        return "\n".join(extra_context) if extra_context else ""

    def _is_user_access_allowed(self):
        self.ensure_one()
        return self.env.user._is_internal()

    @ormcache('self.env.uid', 'self.env.company.id')
    def _get_available_menus(self):
        """Get all menus accessible to the current user as CSV data."""
        all_menus = self.env["ir.ui.menu"].load_web_menus(False)
        root_menu_ids = set(all_menus["root"]["children"])

        # Collect all non-root action menus
        action_menus = []
        for menu_id, web_menu in all_menus.items():
            if menu_id == "root" or menu_id in root_menu_ids:
                continue

            # Only process menus with valid actions
            if web_menu["actionModel"] == "ir.actions.act_window":
                menu = self.env["ir.ui.menu"].browse(web_menu["id"])
                app_menu = self.env["ir.ui.menu"].browse(web_menu["appID"])

                if not menu.exists():
                    continue

                action = self.env["ir.actions.act_window"].browse(web_menu["actionID"])
                if action.exists() and action.res_model:
                    action_menus.append({
                        "menu": menu,
                        "web_menu": web_menu,
                        "action": action,
                        "app_menu": app_menu,
                    })

        # Menus are already ordered by sequence from load_web_menus(), but we still need to sort
        # by complete_name within each app to maintain proper hierarchy display
        action_menus.sort(key=lambda m: (m["app_menu"].sequence, m["menu"].complete_name))

        csv_result = "id|action_id|app|complete_name|model|model_description|available_view_types|default_view_type\n"

        for menu_data in action_menus:
            menu = menu_data["menu"]
            action = menu_data["action"]

            model_description = self.env[action.res_model]._description
            available_view_types = [view[1] for view in action.views] if action.views else []
            default_view_type = available_view_types[0] if available_view_types else "null"
            if action.view_id:
                default_view_type = action.view_id.type

            csv_result += (
                f"{menu.id}|"
                f"{action.id}|"
                f"{menu_data['app_menu'].name}|"
                f"{menu.complete_name}|"
                f"{action.res_model}|"
                f"{model_description}|"
                f"{','.join(available_view_types)}|"
                f"{default_view_type}\n"
            )

        return dedent(f"""
            ## Available Menus
            Lists all menus accessible to the current user with their associated models and views.
            Essential for finding the right menu to open based on user queries.

            Format: CSV with pipe (|) delimiter
            ```
            id|action_id|app|complete_name|model|model_description|available_view_types|default_view_type
            161|986|Accounting|Accounting/Customers/Invoices|account.move|Journal Entry|list,kanban,form,activity|list
            456|1053|Reporting|Reporting/Sales|sale.report|Sales Analysis|graph,pivot,list,form|graph
            ```

            Fields:
            - `id`: Menu identifier (use this for opening menus)
            - `action_id`: Action identifier (use this for referencing actions)
            - `app`: Root application name (e.g., Sales, Accounting, Reporting)
            - `complete_name`: Full menu path with / separators
            - `model`: Technical model name (e.g., 'sale.order', 'product.product')
            - `model_description`: Human-readable model name
            - `available_view_types`: Comma-separated supported views
            - `default_view_type`: View shown when menu opens

            ⚠️ IMPORTANT: This list does NOT include context, domain, or search_view details.
            You MUST call get_menu_details tool to retrieve this information before opening any menu.

            💡 Workflow:
            1. Use this list to find relevant menus based on model and available views
            2. Call get_menu_details tool with menu IDs to get context, domain, and search_view
            3. Parse the returned details to understand available filters and groupbys
            4. Call the appropriate open_menu_* tool with the parsed information

            💡 Tip: Prioritize "Reporting" app menus for analytical queries requiring pivot/graph views.

            {csv_result.strip()}

            Note: Use the menu id from this list when calling open_menu_* tools.
        """).strip()

    @ormcache('self.env.uid', 'self.env.company.id')
    def _get_available_models(self) -> str:
        """Get all models accessible to the current user as CSV data, excluding transient and abstract models."""
        # Get models the user has read access to
        allowed_models = self.env["ir.model.access"]._get_allowed_models(mode="read")

        # Get ir.model records for allowed models, excluding transient
        search_domain = [
            ("model", "in", list(allowed_models)),
            ("transient", "=", False),
        ]
        model_records = self.env["ir.model"].sudo().search(search_domain, order="model")

        # Get app ordering from web menus
        all_menus = self.env["ir.ui.menu"].load_web_menus(False)
        root_menu_ids = all_menus["root"]["children"]  # This is ordered by sequence

        # Create app name to sequence mapping
        app_sequence = {}
        for idx, menu_id in enumerate(root_menu_ids):
            if menu_id in all_menus:
                app_menu = self.env["ir.ui.menu"].browse(all_menus[menu_id]["id"])
                if app_menu.exists():
                    # Get the technical name (usually matches module name)
                    app_name = all_menus[menu_id].get("xmlid", "").split(".")[0]
                    if app_name:
                        app_sequence[app_name] = idx

        # Group models by their main module/app
        models_by_app = defaultdict(list)
        for model_rec in model_records:
            # Skip models without a proper registry entry
            if model_rec.model not in self.env:
                continue

            model_obj = self.env[model_rec.model]
            # Skip models that are actually abstract despite the flag
            if model_obj._abstract or not model_obj._auto:
                continue

            # Determine the app/module (first module in the list)
            modules = model_rec.modules.split(", ") if model_rec.modules else []
            app = modules[0] if modules else "base"

            models_by_app[app].append(
                {
                    "model": model_rec.model,
                    "description": model_rec.name or model_obj._description,
                }
            )

        # Build CSV result
        csv_result = "model|description|module\n"

        # Sort apps by their menu sequence, with unknown apps at the end
        sorted_apps = sorted(
            models_by_app.keys(), key=lambda x: (app_sequence.get(x, 999), x)
        )

        for app in sorted_apps:
            for model_info in sorted(models_by_app[app], key=lambda x: x["model"]):
                csv_result += (
                    f"{model_info['model']}|{model_info['description']}|{app}\n"
                )

        return dedent(f"""
            ## Available Models
            Lists all models accessible to the current user.
            Helps identify which models to inspect when building complex queries.

            Format: CSV with pipe (|) delimiter
            ```
            model|description|module
            sale.order|Sales Order|sale
            project.project|Project|project
            project.task|Task|project
            res.partner|Contact|base
            ```

            Fields:
            - `model`: Technical model name (e.g., 'sale.order', 'res.partner')
            - `description`: Human-readable model name
            - `module`: Primary module/app where model is defined

            💡 Tip: When queries involve multiple entities, immediately call get_fields tool in PARALLEL for all relevant models to discover relationships efficiently.

            {csv_result.strip()}
        """).strip()

    def _get_date_calculation_reference(self):
        """Generate dynamic date calculation reference based on today's date."""
        today = fields.Date.context_today(self)
        today_dt = datetime.strptime(str(today), "%Y-%m-%d")

        # Calculate various date references
        yesterday = today_dt - timedelta(days=1)
        tomorrow = today_dt + timedelta(days=1)
        last_week_start = today_dt - timedelta(days=7)

        # This week (Monday to Sunday)
        days_since_monday = today_dt.weekday()
        this_week_start = today_dt - timedelta(days=days_since_monday)
        days_until_sunday = 6 - days_since_monday
        this_week_end = today_dt + timedelta(days=days_until_sunday)

        # This month (first to last day)
        this_month_start = today_dt.replace(day=1)
        # Get last day of current month
        if today_dt.month == 12:
            next_month_start = today_dt.replace(year=today_dt.year + 1, month=1, day=1)
        else:
            next_month_start = today_dt.replace(month=today_dt.month + 1, day=1)
        this_month_end = next_month_start - timedelta(days=1)

        # Last month
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        # Last 30 days
        thirty_days_ago = today_dt - timedelta(days=30)

        # This year (January 1 to December 31)
        this_year_start = today_dt.replace(month=1, day=1)
        this_year_end = today_dt.replace(month=12, day=31)

        # Last year
        last_year_start = this_year_start.replace(year=today_dt.year - 1)
        last_year_end = this_year_start - timedelta(days=1)

        # Current quarter (full quarter)
        quarter = (today_dt.month - 1) // 3 + 1
        quarter_starts = {
            1: today_dt.replace(month=1, day=1),
            2: today_dt.replace(month=4, day=1),
            3: today_dt.replace(month=7, day=1),
            4: today_dt.replace(month=10, day=1),
        }
        current_quarter_start = quarter_starts[quarter]

        # Calculate end of current quarter
        quarter_ends = {
            1: today_dt.replace(month=3, day=31),
            2: today_dt.replace(month=6, day=30),
            3: today_dt.replace(month=9, day=30),
            4: today_dt.replace(month=12, day=31),
        }
        current_quarter_end = quarter_ends[quarter]

        # Last quarter
        last_quarter = quarter - 1 if quarter > 1 else 4
        last_quarter_year = today_dt.year if quarter > 1 else today_dt.year - 1
        quarter_starts_months = {
            1: 1,   # January
            2: 4,   # April
            3: 7,   # July
            4: 10,  # October
        }
        quarter_ends = {
            1: (3, 31),   # March 31
            2: (6, 30),   # June 30
            3: (9, 30),   # September 30
            4: (12, 31),  # December 31
        }
        start_month = quarter_starts_months[last_quarter]
        last_quarter_start = datetime(last_quarter_year, start_month, 1)
        end_month, end_day = quarter_ends[last_quarter]
        last_quarter_end = datetime(last_quarter_year, end_month, end_day)

        return dedent(f"""
            ## Date Calculation Quick Reference
            Given today is {today}:
            - "yesterday" = {yesterday.strftime('%Y-%m-%d')}
            - "tomorrow" = {tomorrow.strftime('%Y-%m-%d')}
            - "last week" = {last_week_start.strftime('%Y-%m-%d')} to {today}
            - "this week" = {this_week_start.strftime('%Y-%m-%d')} to {this_week_end.strftime('%Y-%m-%d')}
            - "last month" = {last_month_start.strftime('%Y-%m-%d')} to {last_month_end.strftime('%Y-%m-%d')}
            - "this month" = {this_month_start.strftime('%Y-%m-%d')} to {this_month_end.strftime('%Y-%m-%d')}
            - "last 30 days" = {thirty_days_ago.strftime('%Y-%m-%d')} to {today}
            - "this year" = {this_year_start.strftime('%Y-%m-%d')} to {this_year_end.strftime('%Y-%m-%d')}
            - "last year" = {last_year_start.strftime('%Y-%m-%d')} to {last_year_end.strftime('%Y-%m-%d')}
            - "this quarter (Q{quarter})" = {current_quarter_start.strftime('%Y-%m-%d')} to {current_quarter_end.strftime('%Y-%m-%d')}
            - "last quarter (Q{last_quarter})" = {last_quarter_start.strftime('%Y-%m-%d')} to {last_quarter_end.strftime('%Y-%m-%d')}

            Use these exact dates when building custom domains for date-based queries.
        """).strip()

    def _ai_tool_get_fields(self, model_name, include_description=True):
        if not isinstance(model_name, str):
            raise TypeError("Model name must be a string.")

        if not model_name:
            raise ValueError("Model name must be provided.")

        if model_name not in self.env:
            raise ValueError(f"Model '{model_name}' not found.")

        model = self.env[model_name]
        model_fields = model.fields_get()
        results = []

        # Add header
        if include_description:
            results.append("field_name|display_name|type|sortable|groupable|description")
        else:
            results.append("field_name|display_name|type|sortable|groupable")

        for field_name, field_info in model_fields.items():
            if not model._fields[field_name]._description_searchable:
                continue
            field_type = field_info.get('type', 'unknown')
            field_relation = field_info.get('relation', '')
            field_display_name = field_info.get('string', '')
            sortable = str(field_info.get('sortable', False)).lower()
            groupable = str(field_info.get('groupable', False)).lower()
            if field_relation:
                field_type += f"({field_relation})"
            if field_type == 'selection':
                selection_items = field_info.get('selection', [])
                field_type += f"({dict(selection_items)})"
            # Format as CSV with pipe delimiter: field_name|display_name|type|sortable|groupable|description
            field_str = f"{field_name}|{field_display_name}|{field_type}|{sortable}|{groupable}"
            if include_description:
                if description := field_info.get('help', ''):
                    # Replace any pipe characters in the description to avoid delimiter conflicts
                    safe_description = description.replace('|', '&#124;')
                    field_str += f"|{safe_description}"
                else:
                    field_str += "|"  # Empty description column for consistent format
            results.append(field_str)

        return "\n".join(results)

    def _ai_tool_open_menu_list(self, menu_id, model_name, selected_filters, selected_groupbys, search, custom_domain=None):
        validate_search_terms(search)
        validate_groupbys(self.env[model_name], selected_groupbys)

        menus = self.env["ir.ui.menu"].load_menus(debug=request.session.debug)
        menu = menus.get(menu_id)
        if not menu:
            raise ValueError(f"Menu with ID {menu_id} not found.")
        action = self.env["ir.actions.act_window"].browse(menu["action_id"])
        if not action.exists():
            raise ValueError(f"The action associated with menu ID {menu_id} does not exist.")

        action_dict = action._get_action_dict()
        if action_dict.get("res_model") != model_name:
            raise ValueError(f"The model '{model_name}' does not match the model of the action associated with menu ID {menu_id}.")

        available_views = [view[1] for view in action_dict.get("views", [])]
        if "list" not in available_views:
            raise ValueError(f"List view is not available for the action associated with menu ID {menu_id}.")

        bus_data = {
            "menuID": menu_id,
            "selectedFilters": selected_filters,
            "selectedGroupBys": selected_groupbys,
            "search": search,
        }

        if self.env.context.get("ai_session_identifier"):
            bus_data["aiSessionIdentifier"] = self.env.context["ai_session_identifier"]

        if domain := self._parse_domain(model_name, custom_domain):
            bus_data["customDomain"] = domain

        self.env.user._bus_send("AI_OPEN_MENU_LIST", bus_data)

    def _ai_tool_open_menu_kanban(self, menu_id, model_name, selected_filters, selected_groupbys, search, custom_domain=None):
        validate_search_terms(search)
        validate_groupbys(self.env[model_name], selected_groupbys)

        menus = self.env["ir.ui.menu"].load_menus(debug=request.session.debug)
        menu = menus.get(menu_id)
        if not menu:
            raise ValueError(f"Menu with ID {menu_id} not found.")
        action = self.env["ir.actions.act_window"].browse(menu["action_id"])
        if not action.exists():
            raise ValueError(f"The action associated with menu ID {menu_id} does not exist.")

        action_dict = action._get_action_dict()
        if action_dict.get("res_model") != model_name:
            raise ValueError(f"The model '{model_name}' does not match the model of the action associated with menu ID {menu_id}.")

        available_views = [view[1] for view in action_dict.get("views", [])]
        if "kanban" not in available_views:
            raise ValueError(f"Kanban view is not available for the action associated with menu ID {menu_id}.")

        bus_data = {
            "menuID": menu_id,
            "selectedFilters": selected_filters,
            "selectedGroupBys": selected_groupbys,
            "search": search,
        }

        if self.env.context.get("ai_session_identifier"):
            bus_data["aiSessionIdentifier"] = self.env.context["ai_session_identifier"]

        if domain := self._parse_domain(model_name, custom_domain):
            bus_data["customDomain"] = domain

        self.env.user._bus_send("AI_OPEN_MENU_KANBAN", bus_data)

    def _ai_tool_open_menu_pivot(self, menu_id, model_name, selected_filters, row_groupbys, col_groupbys, measures, search, custom_domain=None):
        validate_search_terms(search)
        validate_groupbys(self.env[model_name], row_groupbys)
        validate_groupbys(self.env[model_name], col_groupbys)

        menus = self.env["ir.ui.menu"].load_menus(debug=request.session.debug)
        menu = menus.get(menu_id)
        if not menu:
            raise ValueError(f"Menu with ID {menu_id} not found.")
        action = self.env["ir.actions.act_window"].browse(menu["action_id"])
        if not action.exists():
            raise ValueError(f"The action associated with menu ID {menu_id} does not exist.")

        # Log menu and action details
        menu_obj = self.env["ir.ui.menu"].browse(menu_id)
        _logger.info("Opening pivot view for menu '%s' (ID: %s) with action '%s' (ID: %s)",
                     menu_obj.name, menu_id, action.name, action.id)

        action_dict = action._get_action_dict()
        if action_dict.get("res_model") != model_name:
            raise ValueError(f"The model '{model_name}' does not match the model of the action associated with menu ID {menu_id}.")

        # Parse measures and extract ordering information
        parsed_measures = []
        sorted_column = None
        for measure_str in measures:
            measure_parts = measure_str.strip().split()
            measure_name = measure_parts[0]

            if len(measure_parts) > 1:
                order_part = measure_parts[1].lower()
                if order_part in ['asc', 'desc']:
                    order = order_part
                    # Set the first measure with ordering as the sorted column
                    if sorted_column is None:
                        sorted_column = {
                            'measure': measure_name,
                            'order': order
                        }
                else:
                    raise ValueError(f"Invalid ordering specification '{measure_parts[1]}' for measure '{measure_name}'. Use 'asc' or 'desc'.")

            parsed_measures.append(measure_name)

        # Validate measures
        for measure in parsed_measures:
            if measure != "__count" and measure not in self.env[model_name]._fields:
                raise ValueError(f"Measure '{measure}' not found in model '{model_name}' for menu ID {menu_id}.")

        # Check if pivot view is in available views
        available_views = [view[1] for view in action_dict.get("views", [])]
        if "pivot" not in available_views:
            raise ValueError(f"Pivot view is not available for the action associated with menu ID {menu_id}.")

        bus_data = {
            "menuID": menu_id,
            "model": model_name,
            "selectedFilters": selected_filters or [],
            "rowGroupBys": row_groupbys or [],
            "colGroupBys": col_groupbys or [],
            "measures": parsed_measures or [],
            "search": search or [],
        }

        if self.env.context.get("ai_session_identifier"):
            bus_data["aiSessionIdentifier"] = self.env.context["ai_session_identifier"]

        # Add sorting information if available
        if sorted_column:
            bus_data["sortedColumn"] = sorted_column

        if domain := self._parse_domain(model_name, custom_domain):
            bus_data["customDomain"] = domain

        self.env.user._bus_send("AI_OPEN_MENU_PIVOT", bus_data)

    def _ai_tool_open_menu_graph(
        self, menu_id, model_name, selected_filters, selected_groupbys, measure, mode, order, search,
        stacked=False, cumulated=False, custom_domain=None):
        """
        Opens a graph view for the specified menu ID with the given parameters.
        """
        validate_search_terms(search)
        validate_groupbys(self.env[model_name], selected_groupbys)

        debug = request.session.debug if request else True
        menus = self.env["ir.ui.menu"].load_menus(debug=debug)
        menu = menus.get(menu_id)
        if not menu:
            raise ValueError(f"Menu with ID {menu_id} not found.")
        action = self.env["ir.actions.act_window"].browse(menu["action_id"])
        if not action.exists():
            raise ValueError(f"The action associated with menu ID {menu_id} does not exist.")

        # Log menu and action details
        menu_obj = self.env["ir.ui.menu"].browse(menu_id)
        _logger.info("Opening graph view for menu '%s' (ID: %s) with action '%s' (ID: %s)",
                     menu_obj.name, menu_id, action.name, action.id)

        action_dict = action._get_action_dict()
        if action_dict.get("res_model") != model_name:
            raise ValueError(f"The model '{model_name}' does not match the model of the action associated with menu ID {menu_id}.")

        # Validate measure
        if measure != "__count" and measure not in self.env[model_name]._fields:
            raise ValueError(f"Measure '{measure}' not found in model '{model_name}' for menu ID {menu_id}.")

        # Validate mode
        if mode not in ["bar", "line", "pie"]:
            raise ValueError(f"Invalid mode '{mode}'. Must be 'bar', 'line', or 'pie'.")

        # Validate order
        if order not in ["ASC", "DESC"]:
            raise ValueError(f"Invalid order '{order}'. Must be 'ASC' or 'DESC'.")

        # Check if graph view is in available views
        available_views = [view[1] for view in action_dict.get("views", [])]
        if "graph" not in available_views:
            raise ValueError(f"Graph view is not available for the action associated with menu ID {menu_id}.")

        bus_data = {
            "menuID": menu_id,
            "selectedFilters": selected_filters,
            "groupBys": selected_groupbys or [],
            "measure": measure,
            "mode": mode,
            "order": order,
            "stacked": stacked,
            "cumulated": cumulated,
            "search": search or [],
        }

        if self.env.context.get("ai_session_identifier"):
            bus_data["aiSessionIdentifier"] = self.env.context["ai_session_identifier"]

        if domain := self._parse_domain(model_name, custom_domain):
            bus_data["customDomain"] = domain

        self.env.user._bus_send("AI_OPEN_MENU_GRAPH", bus_data)

    def _ai_tool_compute_report_measures(self, action_id, model):
        if model not in self.env:
            raise ValueError(f"Model '{model}' not found.")

        action = self.env["ir.actions.act_window"].browse(action_id)
        if not action.exists():
            raise ValueError(f"The action associated with menu ID {action_id} does not exist.")

        action_dict = action._get_action_dict()
        if action_dict.get("res_model") != model:
            raise ValueError(f"The model '{model}' does not match the model of the action associated with menu ID {action_id}.")

        # Get field definitions
        model_obj = self.env[model]
        fields = model_obj.fields_get()

        # Get view information to determine field attributes
        views = model_obj.get_views(
            [*action_dict["views"]],
            options={
                "action_id": action.id,
                "toolbar": False,
            },
        )["views"]

        # Extract field attributes from pivot view if available
        field_attrs = {}
        pivot_view = views.get("pivot")
        if pivot_view and pivot_view.get("arch"):
            view_tree = etree.fromstring(pivot_view["arch"], None)
            for field_element in view_tree.xpath(".//field"):
                field_name = field_element.get("name")
                if field_name:
                    field_attrs[field_name] = {
                        "isInvisible": field_element.get("invisible") == "1",
                        "string": field_element.get("string"),
                    }

        # Compute measures using our Python implementation
        measures = compute_report_measures(fields, field_attrs)

        # Convert measures to CSV format with pipe delimiter
        csv_result = "field_name|field_display_name|field_type|aggregator|sortable\n"

        for field_name, field_info in measures.items():
            field_display_name = field_info.get("string", "")
            field_type = field_info.get("type", "")
            aggregator = field_info.get("aggregator", "")
            sortable = str(field_info.get("sortable", "")).lower()

            csv_result += f"{field_name}|{field_display_name}|{field_type}|{aggregator}|{sortable}\n"

        return csv_result.strip()

    def _ai_tool_get_menu_details(self, menu_ids):
        if not isinstance(menu_ids, list):
            raise TypeError("menu_ids must be a list of menu IDs.")

        if not menu_ids:
            raise ValueError("At least one menu ID must be provided.")

        # Load all menus to validate IDs
        menus = self.env["ir.ui.menu"].load_menus(False)

        csv_result = "menu_id|model|context|domain|search_view\n"

        for menu_id in menu_ids:
            if not isinstance(menu_id, (int, float)):
                csv_result += f"{menu_id}|Error: Menu ID must be a number|\n"
                continue

            menu_id = int(menu_id)
            menu = menus.get(menu_id)

            if not menu:
                csv_result += f"{menu_id}|Error: Menu not found|\n"
                continue

            action = self.env["ir.actions.act_window"].browse(menu["action_id"])
            if not action.exists():
                csv_result += f"{menu_id}|Error: Action not found|\n"
                continue

            # Get context and domain
            context_str = str(action.context or {})
            domain_str = str(action.domain or [])

            search_view = self.env[action.res_model].get_view(action.search_view_id.id, 'search')
            search_view_xml = clean_search_view_xml(search_view['arch']) if search_view else ""

            # Escape the XML for CSV - replace quotes and newlines
            if search_view_xml:
                search_view_xml = search_view_xml.replace('\n', ' ').replace('\r', '')

            csv_result += (
                f"{menu_id}|"
                f"{action.res_model}|"
                f"{context_str}|"
                f"{domain_str}|"
                f"{search_view_xml}\n"
            )

        return csv_result.strip()

    def _ai_tool_search(self, model_name, domain="", fields: list[str] | None = None, offset: int = 0, limit: int | None = None, order: str | None = None):
        try:
            parsed_domain = json.loads(domain)
            search_result = self.env[model_name].search_read(parsed_domain, fields, offset, limit, order)
            return search_result
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for custom domain: {e}")

    def _ai_tool_read_group(self, model_name, domain, groupby: list[str] = [], aggregates: list[str] = [], having: str = "[]", offset: int = 0, limit: int | None = None, order: str | None = None):
        try:
            parsed_domain = json.loads(domain)
            parsed_having = ""
            if having:
                parsed_having = json.loads(having)
            result = self.env[model_name]._read_group(parsed_domain, groupby, aggregates, parsed_having, offset, limit, order)
            return result
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format for custom domain: {e}")

    def _ai_tool_adjust_search(self, model_name, remove_facets=None, toggle_filters=None, toggle_groupbys=None, apply_searches=None, measures=None, mode=None, order=None, stacked=None, cumulated=None, custom_domain=None, switch_view_type=None):
        validate_search_terms(apply_searches)
        validate_groupbys(self.env[model_name], toggle_groupbys)

        payload = {
            "removeFacets": remove_facets or [],
            "toggleFilters": toggle_filters or [],
            "toggleGroupBys": toggle_groupbys or [],
            "applySearches": apply_searches or [],
            "measures": measures or [],
            "mode": mode or None,
            "order": order or "ASC",
            "stacked": stacked or False,
            "cumulated": cumulated or False,
            "switchViewType": switch_view_type or False
        }

        available_view_types = self.env.context.get("current_view_info", {}).get("available_view_types", [])
        if switch_view_type and switch_view_type not in available_view_types:
            raise ValueError(f"Requested view type '{switch_view_type}' is not in the available_view_types: {available_view_types}")

        if self.env.context.get("ai_session_identifier"):
            payload["aiSessionIdentifier"] = self.env.context["ai_session_identifier"]

        if domain := self._parse_domain(model_name, custom_domain):
            payload["customDomain"] = domain

        self.env.user._bus_send("AI_ADJUST_SEARCH", payload)
