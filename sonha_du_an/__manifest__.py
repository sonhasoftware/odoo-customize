# -*- coding: utf-8 -*-
{
    'name': 'Sơn Hà dự án',
    'version': '1.7',
    'category': 'sonha du an',
    'summary': 'sonha du an',
    'website': 'https://hrm.sonha.com.vn/',
    'description': "sonha du an",
    'depends': ['base', 'project'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/nhap_lieu_du_an_views.xml',
        'views/project_task_status_views.xml',
        'views/group_du_an_views.xml',
        'wizard/project_task_pending_wizard_views.xml',
        'wizard/bao_cao_du_an_wizard_views.xml',
        'wizard/bao_cao_du_an_cha_wizard_views.xml',
        'views/bao_cao_du_an_views.xml',
        'views/bao_cao_du_an_cha_views.xml',
        'views/project_base_menu.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sonha_du_an/static/src/css/style.css',
            'sonha_du_an/static/src/js/preserve_whitespace_field.js',
            'sonha_du_an/static/src/xml/preserve_whitespace_field.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
