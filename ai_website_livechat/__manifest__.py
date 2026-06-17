{
    'name': "AI Website Livechat Integration",
    'version': '1.0',
    'category': 'Hidden',
    'summary': "AI website livechat components for web builder",
    'depends': ['ai_website', 'ai_livechat', 'html_builder'],
    'data': [
        'views/snippets/snippets.xml',
        'views/snippets/s_ai_livechat.xml',
    ],
    'assets': {
        'im_livechat.assets_embed_core': [
            'ai_website_livechat/static/src/discuss/core/common/**/*',
        ],
        'web.assets_frontend': [
            'web/static/lib/dompurify/DOMpurify.js',
            'ai_website_livechat/static/src/website/components/**/*',
            'ai_website_livechat/static/src/website/interactions/*',
        ],
        'website.assets_inside_builder_iframe': [
            'ai_website_livechat/static/src/website/interactions/edit/**/*',
        ],
        'website.website_builder_assets': [
            'ai_website_livechat/static/src/website/plugins/**/*',
        ],
    },
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
