from odoo import models

class Store:
    def __init__(self):
        self.data = {}
    def add_global_values(self, **kwargs):
        pass
    def add(self, obj, **kwargs):
        pass
    def get_result(self):
        return {}
from odoo.addons.im_livechat.models.discuss_channel import is_livechat_channel


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    def _forward_scripted_chatbot(self, chatbot_script_id):
        # sudo - discuss.channel: let the AI Agent proceed to the forward step (change channel operator, add scripted chatbot
        # as member, remove AI Agent from channel and finally rename channel).
        channel_sudo = self.sudo()
        ai_agent_partner_id = channel_sudo.sudo().ai_agent_id.partner_id

        # add the scripted chatbot to the channel and post a "chatbot invited to the channel" notification
        channel_sudo._add_new_members_to_channel(
            create_member_params={'livechat_member_type': 'bot'},
            inviting_partner=ai_agent_partner_id,
            partners=chatbot_script_id.operator_partner_id,
        )

        channel_sudo._action_unfollow(partner=ai_agent_partner_id, post_leave_message=False)

        # finally, rename the channel to include the scripted chatbot's name
        channel_sudo._update_forwarded_channel_data(
            livechat_failure="no_failure",
            livechat_operator_id=chatbot_script_id.operator_partner_id,
            operator_name=chatbot_script_id.title
        )
        posted_messages = chatbot_script_id.with_context(lang=chatbot_script_id._get_chatbot_language())._post_welcome_steps(self)
        self.channel_pin(pinned=True)
        return posted_messages

    def _update_forwarded_channel_data(self, **kwargs):
        super()._update_forwarded_channel_data(**kwargs)
        self.sudo().ai_agent_id = False

    def _get_allowed_channel_member_create_params(self):
        return super()._get_allowed_channel_member_create_params() + ["ai_agent_id"]

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [Store.One("ai_agent_id", predicate=is_livechat_channel, sudo=True)]

    def _sync_field_names(self):
        field_names = super()._sync_field_names()
        field_names[None].append(Store.One("ai_agent_id", predicate=is_livechat_channel, sudo=True))
        return field_names
