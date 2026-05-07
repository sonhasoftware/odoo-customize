# -*- coding: utf-8 -*-
{
    "name": "Internal Purchase Request (IPR)",
    "version": "17.0.1.0.0",
    "category": "Purchase",
    "summary": "Quản lý yêu cầu mua hàng nội bộ",
    "description": """
        Module quản lý phiếu yêu cầu mua hàng nội bộ:
        - Tạo phiếu yêu cầu theo nhân viên / phòng ban
        - Workflow duyệt đa cấp
        - Multi-company support
        - Phân quyền theo nhóm
    """,
    "author": "Your Company",
    "depends": [
        "base",
        "hr",
        "mail",
        "product",
        "web",
    ],
    "data": [
        # Security
        "security/ipr_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/ir_sequence_data.xml",
        # Views
        "views/ipr_dashboard_action.xml",
        "views/ipr_request_views.xml",
        "views/hr_employee_views.xml",
        "views/ipr_menus.xml",
        # Wizard
        "wizard/ipr_approval_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ipr_purchase/static/src/css/ipr_dashboard.css",
            "ipr_purchase/static/src/components/ipr_dashboard.js",
            "ipr_purchase/static/src/components/ipr_dashboard.xml",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
