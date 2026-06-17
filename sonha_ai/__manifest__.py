# -*- coding: utf-8 -*-
{
    'name': 'Sonha AI Assistant (Ask AI)',
    'version': '1.0',
    'category': 'Productivity/AI',
    'summary': 'AI Assistant integrated with Odoo like Odoo 19',
    'description': """
        Sonha AI Assistant brings an intelligent, context-aware AI chat interface 
        to Odoo 17, inspired by Odoo 19's Ask AI.
        Features:
        - Systray integration
        - Chat window with glassmorphism design
        - Context-aware prompting
        - Direct interaction with Chatter
    """,
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/ai_bot_data.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sonha_ai/static/src/scss/ai_style.scss',
            'sonha_ai/static/src/xml/ai_systray.xml',
            'sonha_ai/static/src/xml/ai_chat_window.xml',
            'sonha_ai/static/src/js/ai_systray.js',
            'sonha_ai/static/src/js/ai_chat_window.js',
            'sonha_ai/static/src/js/ai_command_palette.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
