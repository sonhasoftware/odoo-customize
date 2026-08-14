# -*- coding: utf-8 -*-
from odoo import models


class BaoCaoGhiChuLineMixin(models.AbstractModel):
    _name = 'bao.cao.ghi.chu.line.mixin'
    _description = 'Mixin đồng bộ ghi chú báo cáo → bao.cao.ghi.chu'

    def write(self, vals):
        res = super().write(vals)
        if 'ghi_chu' in vals and not self.env.context.get('skip_bao_cao_ghi_chu_sync'):
            self._sync_ghi_chu_to_master()
        return res

    def _sync_ghi_chu_to_master(self):
        raise NotImplementedError

    def _ghi_chu_master(self):
        return self.env['bao.cao.ghi.chu'].sudo()

    def _ghi_chu_period_key(self, wizard):
        if not wizard or not wizard.period_ids:
            return ''
        return self._ghi_chu_master().period_key_from_periods(wizard.period_ids)
