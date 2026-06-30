# -*- coding: utf-8 -*-
{
    'name': 'Sơn Hà Vật tư',
    'version': '17.0.1.0.1',
    'category': 'Kế hoạch vật tư',
    'summary': 'Lập kế hoạch đặt mua vật tư cần theo kỳ',
    'description': """
      Module kế hoạch đặt mua vật tư
    """,
    'author': 'Sơn Hà',
    'website': 'https://sonha.com.vn',
    'depends': [
        'base', 'mail', 'hr', 'sonha_mdm'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/import_bom_wizard_views.xml',
        'wizard/import_ke_hoach_wizard_views.xml',
        'wizard/import_vat_tu_di_duong_wizard_views.xml',
        'wizard/bao_cao_nhu_cau_vat_tu_wizard_views.xml',
        'views/danh_muc_views.xml',
        'views/bom_views.xml',
        'views/ke_hoach_san_xuat_views.xml',
        'views/dinh_muc_views.xml',
        'views/tinh_toan_vat_tu_views.xml',
        'views/tong_hop_vat_tu_views.xml',
        'views/kh_dat_vat_tu_views.xml',
        'views/vat_tu_di_duong_views.xml',
        'views/ke_hoach_vat_tu_views.xml',
        'views/ke_hoach_workflow_views.xml',
        'views/du_lieu_tong_hop_vat_tu_views.xml',
        'views/bao_cao_nhu_cau_vat_tu_views.xml',
        'views/menu_views.xml',
        'data/cron_jobs.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'sonha_vat_tu/static/src/scss/list_width.scss',
            'sonha_vat_tu/static/src/js/list_free_width.js',
            'sonha_vat_tu/static/src/js/workflow_form_router.js',
            'sonha_vat_tu/static/src/js/vat_tu_chatter_scope.js',
            'sonha_vat_tu/static/src/js/vat_tu_list_header.js',
            'sonha_vat_tu/static/src/xml/vat_tu_list_header.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
