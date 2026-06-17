# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class AIAgent(models.Model):
    _inherit = 'ai.agent'

    created_leads_count = fields.Integer(compute='_compute_created_leads')

    def _compute_created_leads(self):
        lead_count_by_agent = dict(self.env['crm.lead']._read_group(
            [('source_id', 'in', self.mapped('source_id').ids)],
            ['source_id'],
            ['__count']
        ))
        for agent in self:
            self.created_leads_count = lead_count_by_agent.get(agent.source_id)

    def action_view_leads(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'name': self.env._('Leads created by %s', self.name),
            'domain': [('source_id', '=', self.source_id.id)],
            'view_mode': 'kanban,list,graph,pivot,form,calendar,activity',
        }
        return action
