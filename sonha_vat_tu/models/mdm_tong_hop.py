# -*- coding: utf-8 -*-
from odoo import models


class MDMTongHop(models.Model):
    _inherit = 'mdm.tong.hop'

    def write(self, vals):
        res = super().write(vals)
        if 'bom_sale' in vals:
            self._vat_tu_sync_dinh_muc_bom_sale()
        return res

    def _vat_tu_sync_dinh_muc_bom_sale(self):
        bom_sale_id = self.bom_sale.id if self.bom_sale else False
        DinhMuc = self.env['dinh.muc'].sudo()
        for line in self.bang_con_ids:
            code = (line.ma_dv or '').strip()
            if code:
                DinhMuc._patch_bom_sale_for_ma_nvl(code, bom_sale_id)
