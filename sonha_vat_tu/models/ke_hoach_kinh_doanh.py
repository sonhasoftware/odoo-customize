# -*- coding: utf-8 -*-
from odoo import models


class KeHoachKinhDoanh(models.Model):
    _name = 'ke.hoach.kinh.doanh'
    _description = 'Ke hoach kinh doanh'
    _inherit = ['ke.hoach.line.mixin']

    _CHATTER_SCOPE = 'kd'
    _LINE_LABEL = 'kế hoạch kinh doanh'

    _sql_constraints = [
        ('uniq_business_row',
         'unique(period_id, company_id, ma_sap)',
         'Trùng dòng: Kỳ, Đơn vị và Mã phải duy nhất trên kế hoạch kinh doanh!'),
    ]

    def _trigger_production_sync(self):
        if self.env.context.get('skip_kd_sx_sync') or self.env.context.get('is_importing'):
            return
        for period in self.mapped('period_id').filtered(lambda p: p.state == 'ke_hoach'):
            period._sync_production_from_business()

    def _post_create_sync(self):
        self._trigger_production_sync()

    def _post_write_sync(self):
        self._trigger_production_sync()

    def _post_unlink_sync(self, periods):
        for period in periods:
            period._sync_production_from_business()
