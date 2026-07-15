# -*- coding: utf-8 -*-
{
    'name': 'Topic Chatbot (RAG)',
    'version': '17.0.1.0.0',
    'category': 'Productivity/Chatbot',
    'summary': 'Full-screen ChatGPT-like chatbot using Gemini API and RAG with PDF/DOCX documents',
    'description': """
This module implements an independent full-screen chatbot UI resembling ChatGPT.
Users must select a Topic (holding imported documents) before chatting.
It supports:
- PDF and DOCX document uploading and text parsing.
- Automated text chunking.
- Custom full-text keyword-matching retrieval (RAG).
- Gemini API integration.
- Independent chat history per user and topic.
- Permissions: Public topics (Admin-created) and Private topics (User-created).
    """,
    'author': 'Sonha',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/topic_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'topic_chatbot/static/src/components/chat_dashboard/chat_dashboard.js',
            'topic_chatbot/static/src/components/chat_dashboard/chat_dashboard.xml',
            'topic_chatbot/static/src/components/chat_dashboard/chat_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
