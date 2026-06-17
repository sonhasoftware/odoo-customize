{
    'name': "AI Website Integration",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "AI website integration",
    'depends': ['ai', 'website'],
    'data': [
        'data/website_ai_agent.xml',
        'views/snippets/snippets.xml',
    ],
    'assets': {
        'website.assets_editor': [
            'ai_website/static/src/components/dialog/add_page_dialog.js',
            'ai_website/static/src/components/dialog/add_page_dialog.xml',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
