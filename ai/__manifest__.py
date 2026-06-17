# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'AI',
    'version': '1.0',
    'category': 'Hidden',
    'summary': """Base module for AI features""",
    'description': """AI-related features are accessible with limited configurability.""",
    'depends': ['mail'],
    'data': [
        'data/ir_actions_server_data.xml',
        'data/ai_topic_data.xml',
        'security/ir.model.access.csv',
        'security/ai_security.xml',
        'views/res_config_settings_views.xml',
        'views/ir_actions_server_views.xml',
        'views/mail_scheduled_message_views.xml',
        'views/mail_template_views.xml',
        'views/templates.xml',
        'data/ir_cron.xml',
        'data/ai_agent_data.xml',
        'data/ai_composer_data.xml',
        'wizard/mail_compose_message_views.xml',
    ],
    'demo': [
        'data/ai_agent_demo.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('after', 'web/static/src/views/form/form_controller.js', 'ai/static/src/web/form_controller_patch.js'),
            'ai/static/src/**/*',
            ('remove', 'ai/static/src/core/web/lazy/**'),
            ('remove', 'ai/static/src/core/html_editor/**/*'),
            ('remove', 'ai/static/src/worklets/**/*'),
            ('remove', 'ai/static/src/editor/**/*'),
            ('remove', 'ai/static/src/ai_prompt/**/*'),
            ('remove', 'ai/static/src/vad_audio_recorder.js'),
            ('remove', 'ai/static/src/discuss/message_actions_patch.js'),
            ('remove', 'ai/static/src/discuss/thread_actions_patch.js'),
            ('remove', 'ai/static/src/discuss/composer_actions_patch.js'),
            ('remove', 'ai/static/src/discuss/ai_prompt_model.js'),
            ('remove', 'ai/static/src/discuss/thread_model_patch.js'),
        ],
        'web.assets_backend_lazy': [
            'ai/static/src/core/web/lazy/**',
        ],
        'mail.assets_public': [
            'ai/static/src/discuss/core/common/**/*',
        ],
        'portal.assets_chatter_helpers': [
            'ai/static/src/discuss/core/common/**/*',
        ],
        'im_livechat.assets_embed_core': [
            'ai/static/src/discuss/core/common/**/*',
        ],
        'web.assets_unit_tests': [
            'ai/static/tests/**/*',
        ],
    },
    'pre_init_hook': "_pre_init_ai",
    'author': 'Odoo S.A.',
    'license': 'OEEL-1',
}
