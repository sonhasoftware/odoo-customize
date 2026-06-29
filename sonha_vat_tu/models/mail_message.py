# -*- coding: utf-8 -*-
from odoo import api, fields, models


VAT_TU_CHATTER_SCOPES = ('kd', 'sx', 'vt')


class MailMessage(models.Model):
    _inherit = 'mail.message'

    x_vat_tu_scope = fields.Selection(
        selection=[
            ('kd', 'Kế hoạch kinh doanh'),
            ('sx', 'Kế hoạch sản xuất'),
            ('vt', 'Kế hoạch vật tư'),
        ],
        string='Phạm vi chatter vật tư',
        index=True,
    )

    def _message_format_extras(self, format_reply):
        vals = super()._message_format_extras(format_reply)
        vals['x_vat_tu_scope'] = self.x_vat_tu_scope
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        scope = self.env.context.get('vat_tu_chatter_scope')
        if scope in VAT_TU_CHATTER_SCOPES:
            for vals in vals_list:
                model = vals.get('model') or self.env.context.get('default_model')
                if model == 'ke.hoach.vat.tu' and not vals.get('x_vat_tu_scope'):
                    vals['x_vat_tu_scope'] = scope
        return super().create(vals_list)
