# -*- coding: utf-8 -*-
from odoo import models, fields

class MssqlLog(models.Model):
    _name = 'topic_chatbot.mssql_log'
    _description = 'SQL Server Query Log'
    _order = 'create_date desc'

    topic_id = fields.Many2one('topic_chatbot.topic', string='Topic', ondelete='cascade')
    conversation_id = fields.Many2one('topic_chatbot.conversation', string='Conversation', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)
    
    query_text = fields.Text(string='SQL Query')
    is_success = fields.Boolean(string='Success')
    error_msg = fields.Text(string='Error Message')
    execution_time_ms = fields.Integer(string='Execution Time (ms)')
