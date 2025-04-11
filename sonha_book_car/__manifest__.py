# -*- coding: utf-8 -*-
{
    'name': 'Đặt xe Sơn Hà',
    'version': '1.0',
    'category': 'Uncategorized',
    'summary': 'Đặt xe Sơn Hà',
    'website': 'https://',
    'description': "Đặt xe Sơn Hà",
    'depends': ['base', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/book_car_views.xml',
        'views/config_competency_employee_views.xml',
        'views/menu_views.xml',
        'wizard/wizard_exist_car_views.xml',
        'wizard/wizard_return_card_views.xml',
        'wizard/wizard_not_issuing_card_views.xml',
        'wizard/wizard_book_car_report_views.xml',
        'data/mail_template.xml',
    ],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}