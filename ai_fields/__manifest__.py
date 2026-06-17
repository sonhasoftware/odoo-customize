# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': "ai_fields",
    'summary': "Implementation of AI computed fields",
    'description': """
The purpose of this module is to implement AI computed fields, i.e. fields that are computed
using an AI model and a system prompt.
    """,
    'category': 'Hidden',
    'version': '0.1',
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
    'depends': ['ai'],
    'auto_install': True,
    'data': [
        'data/ir_cron_data.xml',
        'views/ir_model_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_fields/static/src/model/**/*',
            'ai_fields/static/src/views/**/*',
        ],
        'web.assets_unit_tests': [
            'ai_fields/static/tests/**/*',
        ],
    },
}
