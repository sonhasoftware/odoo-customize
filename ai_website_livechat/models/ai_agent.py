from odoo import api, fields, models


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    used_on_website_snippet = fields.Boolean()

    @api.model
    def update_website_snippet_agent(self, new_agent_id=None, old_agent_id=None):
        if old_agent := self.env['ai.agent'].with_context(active_test=False).search([('id', '=', old_agent_id)]):
            old_agent.used_on_website_snippet = False
        if new_agent := self.env['ai.agent'].search([('id', '=', new_agent_id)]):
            new_agent.used_on_website_snippet = True

    def _is_user_access_allowed(self):
        return super()._is_user_access_allowed() or self.used_on_website_snippet
