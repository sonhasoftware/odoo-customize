# -*- coding: utf-8 -*-
{
    'name': 'Nhập xuất tồn Sơn Hà',
    'version': '1.7',
    'category': 'Product',
    'summary': 'Nhập xuất tồn Sơn Hà',
    'website': 'https://',
    'description': "Employee Son Ha",
    'depends': ['hr', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/config_status_views.xml',
        'views/input_output_inventory_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}