# -*- coding: utf-8 -*-
{
    'name': 'Sơn Hà Quyền truy cập Menu',
    'version': '1.0',
    'summary': 'Module cấp quyền truy cập vào các menu',
    'author': 'Longnh2',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/menu_access_users_views.xml',
        'views/menu_access_control_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
