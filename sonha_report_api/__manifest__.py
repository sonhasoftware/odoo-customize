# -*- coding: utf-8 -*-
{
    'name': 'Báo CÁO API',
    'version': '1.7',
    'category': 'cat api',
    'summary': 'Báo CÁO API',
    'website': 'https://',
    'description': "Báo CÁO API",
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/config_api_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
