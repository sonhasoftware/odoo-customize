# -*- coding: utf-8 -*-
{
    'name': 'Employee Son Ha',
    'version': '1.7',
    'category': 'Human Resources',
    'summary': 'Son ha Employee',
    'website': 'https://',
    'description': "Employee Son Ha",
    'depends': ['hr', 'base', 'hr_contract'],
    'data': [
        'security/sonha_employee_security.xml',
        'security/ir.model.access.csv',
        'views/sonha_employee_views.xml',
        'views/hr_employee_action.xml',
        'views/hr_contract_view.xml',
        'views/hr_contract_config_view.xml',
        'views/hr_contract_menu.xml',

    ],
    'assets': {
        'web.assets_backend': [
            '/sonha_employee/static/src/template/menu_button_employee.xml'
        ]
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
