# -*- coding: utf-8 -*-
from odoo import api, models

# Chỉ hiện mã (ma_dv) khi Many2one truyền context này — xem bom_dinh_muc_views.xml
CTX_DISPLAY_MA_CODE_ONLY = 'vat_tu_display_ma_code_only'


class MdmTongHopLine(models.Model):
    _inherit = 'mdm.tong.hop.line'

    @api.model
    def _display_ma_code_only(self):
        return bool(self.env.context.get(CTX_DISPLAY_MA_CODE_ONLY))

    @api.model
    def _label_ma_code_only(self, rec):
        return (rec.ma_dv or '').strip() or str(rec.id)

    @api.depends('ma_dv', 'ten')
    def _compute_display_name(self):
        if not self._display_ma_code_only():
            return super()._compute_display_name()
        for rec in self:
            rec.display_name = self._label_ma_code_only(rec)

    def name_get(self):
        if not self._display_ma_code_only():
            return super().name_get()
        return [(rec.id, self._label_ma_code_only(rec)) for rec in self]

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        args = list(args or [])
        if name:
            args += ['|', ('ma_dv', operator, name), ('ten', operator, name)]
        return self._search(args, limit=limit, order=order)
