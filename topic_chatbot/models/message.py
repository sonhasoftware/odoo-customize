# -*- coding: utf-8 -*-
from odoo import fields, models

class TopicChatbotMessage(models.Model):
    _name = 'topic_chatbot.message'
    _description = 'Chatbot Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one(
        'topic_chatbot.conversation', 
        string='Conversation', 
        required=True, 
        ondelete='cascade',
        index=True
    )
    role = fields.Selection([
        ('user', 'User'),
        ('model', 'AI Assistant')
    ], string='Role', required=True)
    content = fields.Text(string='Content', required=True)
    create_date = fields.Datetime(string='Created On', readonly=True)
