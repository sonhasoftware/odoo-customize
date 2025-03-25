# -*- coding: utf-8 -*-
{
    'name': "Bao hanh Son Ha",
    'summary': "",
    'description': "",
    'author': "",
    'website': "",
    'category': '',
    'version': '0.1',
    'depends': [
        'base', 'mail'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/province.xml',
        'views/district.xml',
        'views/ward_commune.xml',
        'views/product_type.xml',
        'views/bh_branch_views.xml',
        'views/produce_year_views.xml',
        'views/error_code_views.xml',
        'views/error_group_views.xml',
        'views/form_exchange_views.xml',
        'views/warranty_status_views.xml',
        'views/staff_warranty_information_views.xml',
        'views/warranty_information_views.xml',
        'views/import_before_repair_views.xml',
        'views/sonha_product_views.xml',
        'views/export_company_views.xml',
        'views/return_customer_views.xml',
        'views/export_warehouse_views.xml',
        'views/transfer_warehouse_views.xml',
        'views/btn_get_transfer_warehouse.xml',
        'wizard/get_transfer_warehouse_views.xml',
        'views/danh_muc.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sonha_baohanh/static/src/js/get_transfer_warehouse.js',
            'sonha_baohanh/static/src/xml/get_transfer_warehouse.xml',
            'sonha_baohanh/static/src/css/style.css'
        ],
    },
    'installable': True,
    'application': True,
}
