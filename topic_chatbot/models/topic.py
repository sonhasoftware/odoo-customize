# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class TopicChatbotTopic(models.Model):
    _name = 'topic_chatbot.topic'
    _description = 'Chatbot Topic'
    _order = 'name'

    name = fields.Char(string='Topic Name', required=True)
    description = fields.Text(string='Description')
    is_public = fields.Boolean(
        string='Is Public', 
        default=False,
        help="If checked, this topic is visible to all users. Only administrators can set this."
    )
    is_admin = fields.Boolean(compute='_compute_is_admin')

    def _compute_is_admin(self):
        is_admin = self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin')
        for rec in self:
            rec.is_admin = is_admin

    document_ids = fields.One2many(
        'topic_chatbot.document', 
        'topic_id', 
        string='Documents'
    )
    chunk_ids = fields.One2many(
        'topic_chatbot.chunk', 
        'topic_id', 
        string='Text Chunks'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('is_public') and not self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin'):
                raise ValidationError("Only administrators can create public topics.")
        return super().create(vals_list)

    def write(self, vals):
        if 'is_public' in vals and vals.get('is_public') and not self.env.user.has_group('topic_chatbot.group_topic_chatbot_admin'):
            raise ValidationError("Only administrators can make topics public.")
        return super().write(vals)
