{
    "name": "ai_server_actions",
    "summary": "Implementation of AI server actions",
    "description": """This module allows you to update record fields with AI, in server actions.""",
    "category": "Hidden",
    "version": "0.1",
    "author": "Odoo S.A.",
    "license": "LGPL-3",
    "depends": ["ai_fields"],
    "auto_install": True,  # TODO merge ai_fields, ai_server_actions into ai in 19
    "data": [
        "views/ir_actions_server_views.xml",
    ],
}
