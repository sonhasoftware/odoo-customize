# -*- coding: utf-8 -*-
from odoo import api, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.depends_context('vat_tu_company_code_display')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('vat_tu_company_code_display'):
            return
        for company in self:
            code = getattr(company, 'company_code', None) or company.name
            company.display_name = code
