# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI',
    'version': '1.0',
    'category': 'Hidden',
    'summary': """
        A powerful suite of AI tools and agents
        integrated directly into your Odoo environment.""",
    'description': """
        * Create and manage AI agents for various business tasks
        * Integrate with popular AI models and services
        * Process documents and extract information automatically
        * Enhance customer service with AI-powered responses
        * Automate routine tasks with intelligent workflows
    """,
    'depends': ['attachment_indexation', 'ai'],
    'data': [
        'views/ai_agent_views.xml',
        'views/ai_topic_views.xml',
        'views/ai_composer_views.xml',
        'views/res_config_settings_views.xml',
        'views/ai_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_app/static/src/**/*',
        ],
        'web.assets_unit_tests': [
            'ai_app/static/tests/**/*',
        ],
    },
    'application': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
