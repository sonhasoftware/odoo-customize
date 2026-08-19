# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.osv import expression


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.depends_context('vat_tu_company_code_display')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('vat_tu_company_code_display'):
            return
        for company in self:
            company.display_name = (company.company_code or '').strip() or company.name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('vat_tu_company_code_display') and name:
            args = expression.AND([
                args or [],
                ['|', ('company_code', operator, name), ('name', operator, name)],
            ])
            name = ''
        return super().name_search(name, args, operator, limit=limit)
