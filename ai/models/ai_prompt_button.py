from odoo import api, fields, models
from odoo.osv import expression

PROMPT_MODULE_MAP = {
    "mass_mailing": ["ai_prompt_optout_reason"],
    "stock": ["ai_prompt_low_stock_pivot", "ai_prompt_stock_move"],
    "sale": [
        "ai_prompt_sales_by_country",
        "ai_prompt_top_sales_reps",
        "ai_prompt_sales_by_category",
        "ai_prompt_top_selling_products_chart",
        "ai_prompt_profit_margin_by_category",
        "ai_prompt_blog_ideas_catalog"
    ],
    "calendar": ["ai_prompt_agenda_today"],
    "project": ["ai_prompt_most_expensive_project"],
    "accounting": ["ai_prompt_cash_flow_status"],
    "helpdesk": ["ai_prompt_top_ticket_cause"],
    "purchase": ["ai_prompt_latest_po_azure"]
}


class AIPromptButton(models.Model):
    _name = "ai.prompt.button"
    _description = "Prompt that can be attached to AI UI rules for quick access by the user."

    name = fields.Char(
        "AI Prompt", help="The prompt sent to the AI when clicked on"
    )
    sequence = fields.Integer(string="Sequence", default=10)
    composer_id = fields.Many2one("ai.composer", index='btree_not_null')

    @api.model
    def _search(self, domain, *args, **kwargs):
        """Only include prompts if their related modules are installed.
           Hack to not have lots of 3-lines bridge modules
        """
        installed_modules = self.env['ir.module.module']._installed()

        # collect ids of prompts whose module are not installed
        skip_ids = []
        for module, record_ref in PROMPT_MODULE_MAP.items():
            if module not in installed_modules:
                for rec_id in record_ref:
                    record = self.env.ref(f"ai.{rec_id}", raise_if_not_found=False)
                    if record:
                        skip_ids.append(record.id)

        if skip_ids:
            domain = expression.AND([[('id', 'not in', skip_ids)], domain])

        return super()._search(domain, *args, **kwargs)
