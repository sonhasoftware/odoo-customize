# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "AI Text Draft - Knowledge",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "AI text draft integration with knowledge",
    'depends': ['ai', 'knowledge'],
    'data': [
        'data/ai_composer_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_knowledge/static/src/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
