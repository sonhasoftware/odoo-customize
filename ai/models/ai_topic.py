# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class AITopic(models.Model):
    # TODO: drop this model and use server action of type AI
    _name = 'ai.topic'
    _description = "Create a topic that leverages instructions and tools to direct Odoo AI in assisting the user with their tasks."

    name = fields.Char(string="Title", required=True)
    description = fields.Text(string="Description")
    instructions = fields.Text(string="Instructions")
    tool_ids = fields.Many2many('ir.actions.server', string="AI Tools", domain=[('use_in_ai', '=', True)])
