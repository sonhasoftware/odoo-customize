from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request
from odoo.tools.mail import html_sanitize
from odoo.addons.mail.models.discuss.mail_guest import add_guest_to_context
from odoo.addons.mail.controllers.thread import ThreadController


class AIController(ThreadController):

    @http.route(["/ai/generate_w_composer"], type="json", auth="user")
    def generate_text(self, prompt, channel_id):
        composer_channel = request.env['discuss.channel'].search([('id', '=', channel_id)], limit=1)
        # remove HTML tags from the prompt (LLMs get confused and format their replies using HTML)
        prompt = html_sanitize(prompt).striptags()
        # generate response by sending prompt to the chatgpt api
        response = composer_channel._ai_submit_to_model(prompt, composer_channel.ai_context)
        # add original prompt to the conversation history (context)
        composer_channel._ai_add_message_to_context(prompt, 'user')
        # post response as odoobot
        composer_channel._ai_create_response(response)

    # auth=public to allow visitors to interact with ai agents through livechat
    @http.route(["/ai/generate_response"], type="json", auth="public")
    @add_guest_to_context
    def generate_response(self, mail_message_id, channel_id, current_view_info=None, ai_session_identifier=None):
        channel = self._get_ai_channel_from_id(channel_id)
        if not channel:
            raise NotFound()
        message = request.env['mail.message'].search([('id', '=', mail_message_id)], limit=1)
        if message:
            channel.sudo().ai_agent_id.with_context(current_view_info=current_view_info, ai_session_identifier=ai_session_identifier)._generate_response_for_channel(message, channel)

    # auth=public to allow visitors to interact with ai agents through livechat
    @http.route(["/ai/post_error_message"], type="json", auth="public")
    @add_guest_to_context
    def post_error_message(self, error_message, channel_id):
        channel = self._get_ai_channel_from_id(channel_id)
        # The channel could have been deleted (the ai chat channel has been closed) so do nothing instead of throwing an error.
        if not channel:
            return
        channel.sudo().ai_agent_id._post_error_message(error_message, channel)

    @http.route('/ai/close_ai_chat', methods=["POST"], type="json", auth='public')
    @add_guest_to_context
    def close_ai_chat(self, channel_id):
        channel = self._get_ai_channel_from_id(channel_id)
        if channel and self._should_unlink_on_close(channel):
            channel.sudo().unlink()

    def _should_unlink_on_close(self, channel):
        return channel.is_member

    def _get_ai_channel_from_id(self, channel_id):
        channel = request.env['discuss.channel'].search([('id', '=', channel_id)])
        if channel.sudo().ai_agent_id:
            return channel
        return request.env['discuss.channel']
