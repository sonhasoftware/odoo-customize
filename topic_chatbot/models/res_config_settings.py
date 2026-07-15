# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    topic_chatbot_gemini_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='topic_chatbot.gemini_api_key'
    )
    topic_chatbot_gemini_model = fields.Selection([
        ('gemini-1.5-flash', 'Gemini 1.5 Flash'),
        ('gemini-1.5-pro', 'Gemini 1.5 Pro'),
        ('gemini-2.0-flash', 'Gemini 2.0 Flash'),
        ('gemini-2.5-flash', 'Gemini 2.5 Flash'),
        ('gemini-2.5-pro', 'Gemini 2.5 Pro'),
    ], string='Gemini Model',
       config_parameter='topic_chatbot.gemini_model',
       default='gemini-1.5-flash',
       help="Select the Gemini model for the chatbot."
    )

