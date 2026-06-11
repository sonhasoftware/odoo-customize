# -*- coding: utf-8 -*-
{
    "name": "Tree View Column Reorder",
    "version": "17.0.1.0.0",
    "category": "Extra Tools",
    "summary": "Drag and drop to reorder columns in all tree/list views",
    "description": "Allow users to drag and drop tree view columns and persist column order per view.",
    "author": "Local Custom",
    "license": "LGPL-3",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "tree_view_column_reorder/static/src/js/list_column_reorder.js",
            "tree_view_column_reorder/static/src/scss/list_column_reorder.scss",
        ],
    },
    "installable": True,
    "application": False,
}
