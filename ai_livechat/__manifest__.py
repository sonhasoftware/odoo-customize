# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI Livechat',
    'version': '1.0',
    'category': 'AI',
    'summary': """
        Augment Livechat with AI Agents.
    """,
    'depends': ['ai_app', 'im_livechat'],
    'data': [
        'data/ai_agent_data.xml',
        'views/im_livechat_channel_rule_views.xml'
    ],
    'demo': [
        'data/im_livechat_channel_rule_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_livechat/static/src/discuss/core/common/**/*',
        ],
        'mail.assets_public': [
            'ai_livechat/static/src/discuss/core/common/**/*',
        ],
        'portal.assets_chatter_helpers': [
            'ai_livechat/static/src/discuss/core/common/**/*',
        ],
        'im_livechat.assets_embed_core': [
            'ai_livechat/static/src/discuss/core/common/**/*',
            'ai_livechat/static/src/discuss/embed/common/**/*',
        ],
        'im_livechat.assets_embed_cors': [
            'ai_livechat/static/src/discuss/embed/cors/**/*',
        ],
    },
    'author': 'Odoo S.A.',
    'installable': True,
    'auto_install': True,
    'license': 'OEEL-1',
}
