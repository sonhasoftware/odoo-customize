# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AIAgent(models.Model):
    _name = 'ai.agent'
    _inherit = [
        'ai.agent',
        'utm.source.mixin',
    ]
    _rec_name = 'name'

    def _auto_init(self):
        res = super()._auto_init()
        for agent in self.search([['source_id', '=', False]]):
            agent.source_id = self.env['utm.source'].create({'name': agent.name}).id
        return res
