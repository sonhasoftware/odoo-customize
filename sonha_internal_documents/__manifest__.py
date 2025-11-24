# -*- coding: utf-8 -*-
{
    'name': 'Văn bản nội bộ Sơn Hà',
    'version': '1.7',
    'category': 'Human Resources',
    'summary': 'Son ha van ban noi bo',
    'website': 'https://',
    'description': "Son ha van ban noi bo",
    'depends': ['base', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/dang_ky_van_ban_views.xml',
        'views/dk_loai_vb_views.xml',
        'views/dk_xu_ly_views.xml',
        'views/bao_cao_van_ban_views.xml',
        'views/bao_cao_tong_hop_views.xml',
        'wizard/wizard_dk_vb_tu_choi_view.xml',
        'wizard/popup_bao_cao_views.xml',
        'wizard/popup_tong_hop_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sonha_internal_documents/static/src/css/save_discard_style.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
