# -*- coding: utf-8 -*-
{
    'name': 'Kho Quyết định & Tài liệu Công ty',
    'version': '17.0.1.2.0',
    'category': 'Documents',
    'summary': 'Lưu trữ và tra cứu quyết định theo danh mục, phòng ban và nhân viên',
    'description': """
Kho lưu trữ quyết định và tài liệu nội bộ:
- Danh mục tài liệu phân cấp.
- Phân loại theo phòng ban và nhân viên.
- Lưu file trong Odoo hoặc liên kết tới kho file bên ngoài.
- Tra cứu theo từ khóa, số quyết định, ngày ban hành và đơn vị liên quan.
    """,
    'author': 'Sonha',
    'depends': ['base', 'mail', 'hr', 'topic_chatbot'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/topic_data.xml',
        'views/decision_category_views.xml',
        'views/decision_document_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

