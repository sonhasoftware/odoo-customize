# -*- coding: utf-8 -*-
from odoo import api, models

_MD_SAP_BOM_TABLE = 'md_sap_bom'
_MD_SAP_TON_KHO_TABLE = 'md_sap_ton_kho'


class APITableSQL(models.Model):
    _inherit = 'api.table.sql'

    @api.model
    def cron_pull_md_sap_ton_kho_monthly(self):
        for rec in self.sudo().search([('table', '=', _MD_SAP_TON_KHO_TABLE)]):
            rec.action_download()

    @api.model
    def cron_pull_md_sap_bom_monthly(self):
        pulled = False
        for rec in self.sudo().search([('table', '=', _MD_SAP_BOM_TABLE)]):
            rec.action_download()
            if not rec.error:
                pulled = True
        if pulled:
            self.env.cr.execute('CALL public.fn_bom_chuoi_cung_ung()')
