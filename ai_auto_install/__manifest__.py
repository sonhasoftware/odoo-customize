# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'AI Auto Install',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Auto install AI module if pgvector is available',
    'description': '''
        This module is needed to conditionally auto install the AI module.
        It checks if the pgvector extension is available in the server and
        only then the AI module is auto-installed.
    ''',
    'depends': ['mail'],
    'auto_install': True,
    'post_init_hook': '_auto_install_ai',
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
