# -*- coding: utf-8 -*-
{
    "name": "Tree View Column Reorder",
    "version": "17.0.1.0.0",
    "category": "Extra Tools",
    "summary": "Drag and drop to reorder columns in all tree/list views",
    "description": "Allow administrators to configure shared list column order, widths and labels per view.",
    "author": "Local Custom",
    "license": "LGPL-3",
    "depends": ["web", "bus"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "tree_view_column_reorder/static/src/js/column_layout_service.js",
            "tree_view_column_reorder/static/src/js/column_label_dialog.js",
            "tree_view_column_reorder/static/src/js/list_column_reorder.js",
            "tree_view_column_reorder/static/src/xml/column_label_editor.xml",
            "tree_view_column_reorder/static/src/scss/list_column_reorder.scss",
        ],
    },
    "installable": True,
    "application": False,
}
