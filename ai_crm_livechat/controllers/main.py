# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.ai.controllers.main import AIController


class AICrmLivechatController(AIController):
    def _should_unlink_on_close(self, channel):
        # allow to check discussions from the leads created by agents in livechats
        if channel.channel_type == 'livechat' and channel.has_crm_lead:
            return False
        return super()._should_unlink_on_close(channel)
