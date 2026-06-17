# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "AI Documents",
    "version": "1.0",
    "category": "Hidden",
    "summary": "Automatically sort your documents.",
    "description": """
        Automatically sort your documents.
        This module is only used to sort documents automatically and cannot be used for any ai-documents related features since it relies on base_automation as well.
        It should be renamed later to ai_documents_automation.
    """,
    "depends": ["ai", "documents", "base_automation"],
    "demo": [
        "demo/ir_actions_server_tools.xml",
    ],
    "data": [
        "data/ir_actions_server_tools.xml",
        "data/ir_cron.xml",
        "views/documents_document_views.xml",
        "security/ir.model.access.csv",
        "wizard/ai_documents_sort.xml",
    ],
    "author": "Odoo S.A.",
    "license": "OEEL-1",
    "assets": {
        "web.assets_backend": [
            "ai_documents/static/src/cog_menu/*",
            "ai_documents/static/src/scss/*",
            "ai_documents/static/src/views/**/*",
            "ai_documents/static/src/views/*",
            "ai_documents/static/src/*",
            ("remove", "ai_documents/static/src/views/activity/**"),
        ],
        "web.assets_backend_lazy": [
            "ai_documents/static/src/views/activity/**",
        ],
    },
    "auto_install": True,
}
