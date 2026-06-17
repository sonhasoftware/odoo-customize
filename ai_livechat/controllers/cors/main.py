# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.http import route
from odoo.addons.ai_livechat.controllers.main import AILivechatController
from odoo.addons.im_livechat.tools.misc import force_guest_env


class CorsLivechatController(AILivechatController):

    @route("/ai_livechat/cors/forward_operator", type="jsonrpc", auth="public", cors="*")
    def cors_forward_operator(self, guest_token, channel_id):
        force_guest_env(guest_token)
        return self.forward_operator(channel_id)
