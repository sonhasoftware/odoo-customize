# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Model Builder',
    'version': '17.0.1.0.0',
    'category': 'Technical',
    'summary': 'Tạo model, view, menu động từ giao diện cấu hình',
    'description': """
        Module cho phép người dùng định nghĩa cấu trúc dữ liệu
        và tự động sinh ra Model (ir.model), View (XML), Menu + Action
        mà không cần lập trình thủ công.
    """,
    'author': 'Dynamic Builder',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/dynamic_model_views.xml',
        'views/dynamic_model_field_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}