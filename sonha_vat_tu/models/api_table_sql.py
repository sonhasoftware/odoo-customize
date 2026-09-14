# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_MD_SAP_TON_KHO_TABLE = 'md_sap_ton_kho'


class APITableSQL(models.Model):
    _inherit = 'api.table.sql'

    @api.model
    def cron_pull_md_sap_ton_kho_monthly(self):
        """Kéo tồn kho SAP — chạy ngày 1 hàng tháng (ir.cron trong sonha_vat_tu)."""
        records = self.sudo().search([('table', '=', _MD_SAP_TON_KHO_TABLE)])
        if not records:
            _logger.warning(
                'cron_pull_md_sap_ton_kho_monthly: không tìm thấy bản ghi api.table.sql '
                'với table=%s',
                _MD_SAP_TON_KHO_TABLE,
            )
            return
        for rec in records:
            _logger.info(
                'cron_pull_md_sap_ton_kho_monthly: kéo dữ liệu bản ghi id=%s table=%s',
                rec.id,
                rec.table,
            )
            rec.action_download()
            if rec.error:
                _logger.warning(
                    'cron_pull_md_sap_ton_kho_monthly: bản ghi id=%s lỗi: %s',
                    rec.id,
                    rec.error,
                )
