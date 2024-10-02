# -*- coding: utf-8 -*-
{
    'name': 'Employee Son Ha',
    'version': '1.7',
    'category': 'Human Resources',
    'summary': 'Son ha Employee',
    'website': 'https://',
    'description': "Employee Son Ha",
    'depends': ['hr', 'base'],
    'data': [
        'security/sonha_employee_security.xml',
        'security/ir.model.access.csv',
        'views/sonha_employee_views.xml',
        'views/hr_employee_action.xml',
        'views/hr_contract_view.xml',
        'views/hr_contract_config_view.xml',
        'views/hr_contract_menu.xml',
        'views/form_config_view.xml',
        'views/level_config_view.xml',
        'views/object_config_view.xml',
        'views/state_config_view.xml',
        'views/title_config_view.xml',
        'views/reward_discipline_config_menu.xml',
        'views/reward_unit_view.xml',
        'views/reward_person_view.xml',
        'views/discipline_unit_view.xml',
        'views/discipline_person_view.xml',
        'views/reward_discipline_menu.xml',

    ],
    'assets': {
        'web.assets_backend': [
            '/sonha_employee/static/src/template/menu_button_employee.xml',
            '/sonha_employee/static/src/css/custom_style.css'
        ]
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
