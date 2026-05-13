# -*- coding: utf-8 -*-
{
    'name': 'Sơn Hà - Vật tư',
    'version': '17.0.1.0.1',
    'category': 'Kế hoạch vật tư',
    'summary': 'Lập kế hoạch đặt mua vật tư cần theo kỳ',
    'description': """
      Module kế hoạch đặt mua vật tư
    """,
    'author': 'Sơn Hà',
    'website': 'https://sonha.com.vn',
    'depends': ['base', 'mail', 'hr', 'uom'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/import_bom_wizard_views.xml',
        'wizard/import_ke_hoach_wizard_views.xml',
        'views/danh_muc_views.xml',
        'views/bom_views.xml',
        'views/ke_hoach_thanh_pham_views.xml',
        'views/dinh_muc_views.xml',
        'views/tinh_toan_vat_tu_views.xml',
        'views/tong_hop_vat_tu_views.xml',
        'views/kh_dat_vat_tu_views.xml',
        'views/vat_tu_di_duong_views.xml',
        'views/ke_hoach_vat_tu_views.xml',
        'views/du_lieu_tong_hop_vat_tu_views.xml',
        'views/menu_views.xml',
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sonha_vat_tu/static/src/scss/list_width.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
