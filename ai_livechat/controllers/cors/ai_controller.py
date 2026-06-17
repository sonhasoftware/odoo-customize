# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import route
from odoo.addons.ai.controllers.main import AIController
from odoo.addons.im_livechat.tools.misc import force_guest_env


class CorsLivechatController(AIController):

    @route(["/ai/cors/generate_response"], type="jsonrpc", auth="public", cors="*")
    def cors_generate_response(self, guest_token, mail_message_id, channel_id):
        force_guest_env(guest_token)
        self.generate_response(mail_message_id, channel_id)

    @route(["/ai/cors/post_error_message"], type="jsonrpc", auth="public", cors="*")
    def cors_post_error_message(self, guest_token, error_message, channel_id):
        force_guest_env(guest_token)
        self.post_error_message(error_message, channel_id)

    @route("/ai/cors/close_ai_chat", type="jsonrpc", auth="public", cors="*")
    def cors_close_ai_chat(self, guest_token, channel_id):
        force_guest_env(guest_token)
        self.close_ai_chat(channel_id)
