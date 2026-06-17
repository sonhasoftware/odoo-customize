# Part of Odoo. See LICENSE file for full copyright and licensing details.
import random

from odoo import _, fields, models, api
from odoo.exceptions import AccessError


class Store:
    def __init__(self):
        self.data = {}
    def add_global_values(self, **kwargs):
        pass
    def add(self, obj, **kwargs):
        pass
    def get_result(self):
        return {}


def is_ai_chat_channel(channel):
    """Predicate to filter channels for which the channel type is 'ai_chat'.

    :returns: Whether the channel is an ai_chat channel.
    :rtype: bool
    """
    return channel.channel_type == "ai_chat"


class DiscussChannel(models.Model):
    """Chat Session
    Representing a conversation between users.
    It extends the base method for usage with AI assistant.
    """

    _name = "discuss.channel"
    _inherit = ["discuss.channel"]

    channel_type = fields.Selection(
        selection_add=[("ai_chat", "AI chat")],
        ondelete={"ai_chat": "cascade"},
    )
    ai_env_context = fields.Json("Context for AI agent")
    # Having ai_agent_id written by users can compromise the security of channels. For example, adding ai_agent_id
    # to a channel will make it garbage collected, a channel member can unlink an ai agent from the channel, etc.
    # Thus, the field has group fields.NO_ACCESS so that the field can only be written in controlled flows.
    ai_agent_id = fields.Many2one("ai.agent", index="btree_not_null", groups=fields.NO_ACCESS)

    _sql_constraints = [
        ('ai_channel_type_check',
         "CHECK(ai_agent_id IS NULL or channel_type = 'ai_chat' or channel_type = 'livechat')",
         'AI Agent can only be set for ai_chat or livechat channels.'),
    ]

    @api.model
    def create_ai_draft_channel(
        self,
        caller_component,
        channel_title=None,
        record_model=None,
        record_id=None,
        front_end_info=None,
        text_selection=None,
    ):
        ai_composer = None
        if record_model:  # if we call the AI within a specific model, we search for composer configs that might include that model and we take the last one
            ai_composer = self.env['ai.composer'].sudo().search([
                ('interface_key', '=', caller_component),
                ('focused_models', 'in', record_model),
            ], limit=1, order="create_date DESC")
        if not ai_composer:  # if we don't find any composer configs or we call the ai from a place with no specific model, fallback to the basic composers
            ai_composer = self.env['ai.composer'].sudo().search([
                ('interface_key', '=', caller_component),
                ('focused_models', '=', False),
            ], limit=1, order="create_date DESC")
        ai_agent = ai_composer.ai_agent
        if not ai_agent:
            raise AccessError(_("AI not reachable, AI Agent not found."))

        channel_name = self.env._("AI: %(name)s", name=channel_title) if channel_title else ai_agent.name
        # create a new AI chat
        channel = ai_agent._create_ai_chat_channel(channel_name=channel_name)
        # Create the initial context for the AI - the default prompt from the composer
        model_context = [
            ai_composer.default_prompt,
        ]

        if record_model:
            original_record = self.env[record_model].browse(record_id)
            # Add extra info that are relevant to the where we call the AI from (record info, chatter info, pre-prompts, etc.)
            model_context += original_record._ai_initialise_context(
                caller_component, text_selection, front_end_info
            )

        # Finally pass the complete "save" the context to the channel
        channel.ai_env_context = model_context

        prompts = ai_composer.available_prompts
        random_prompts = random.sample(prompts, min(3, len(prompts)))

        return {"ai_channel_id": channel.id, "data": {"Thread": channel._channel_info()[0]}, "prompts": [prompt.name for prompt in random_prompts]}

    @api.autovacuum
    def _remove_ai_chat_channels(self):
        # sudo() => ai_agent_id has group fields.NO_ACCESS and the method is only called from cron jobs.
        expired_ai_chats = self.env['discuss.channel'].search([
            ("ai_agent_id", "!=", False),
            ('channel_type', '=', 'ai_chat'),
            ('last_interest_dt', '<', '-1d')
        ]).unlink()

    def _channel_info(self):
        channel_infos = super()._channel_info()
        for info in channel_infos:
            channel = self.browse(info['id'])
            if channel.channel_type == 'ai_chat':
                # sudo() is needed because ai_agent_id has groups=base.group_no_one or similar restricted access
                info['ai_agent_id'] = channel.sudo().ai_agent_id.id
        return channel_infos
