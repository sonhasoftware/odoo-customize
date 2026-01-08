# -*- coding: utf-8 -*-
{
    'name': 'Sơn Hà SAP',
    'version': '1.7',
    'category': 'Uncategorized',
    'summary': 'Sơn Hà SAP',
    'website': 'https://',
    'description': "Sơn Hà SAP",
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/sap_unlock_views.xml',
        'wizard/notice_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}