# -*- coding: utf-8 -*-
from odoo import fields, models

class TopicChatbotConversation(models.Model):
    _name = 'topic_chatbot.conversation'
    _description = 'Chatbot Conversation'
    _order = 'create_date desc'

    name = fields.Char(
        string='Conversation Title', 
        default='New Chat', 
        required=True
    )
    user_id = fields.Many2one(
        'res.users', 
        string='User', 
        required=True, 
        default=lambda self: self.env.user,
        index=True
    )
    topic_id = fields.Many2one(
        'topic_chatbot.topic', 
        string='Topic', 
        required=True, 
        ondelete='cascade'
    )
    message_ids = fields.One2many(
        'topic_chatbot.message', 
        'conversation_id', 
        string='Messages'
    )
