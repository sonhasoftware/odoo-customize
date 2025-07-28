# -*- coding: utf-8 -*-
{
    'name': 'Nước lạng sơn',
    'version': '1.7',
    'category': 'Plan Consume',
    'summary': 'Nước lạng sơn',
    'website': 'https://hrm.sonha.com.vn/',
    'description': "Nước lạng sơn",
    'depends': [],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/config_pumping_views.xml',
        'views/config_branch_views.xml',
        'views/reality_consume_views.xml',
        'views/plan_consume_views.xml',
        'data/cron_job.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
