# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "AI crm livechat",
    "summary": "Automatically create leads from livechat.",
    "description": "Automatically create leads from livechat.",
    "author": "Odoo S.A.",
    "version": "1.0",
    "category": "Hidden",
    "license": "OEEL-1",
    "depends": ["ai_crm", "ai_livechat"],
    "auto_install": True,
    "data": [
        "data/ai_agent.xml",
        "views/ai_agent_views.xml",
    ],
}
