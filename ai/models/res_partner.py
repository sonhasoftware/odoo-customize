# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    agent_ids = fields.One2many("ai.agent", inverse_name="partner_id")

    def _compute_im_status(self):
        agent_partners = self.with_context(active_test=False).filtered(lambda record: record.agent_ids)
        agent_partners.im_status = 'agent'
        super(ResPartner, self - agent_partners)._compute_im_status()
