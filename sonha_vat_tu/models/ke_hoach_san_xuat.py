# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

PRODUCTION_COMPANY_CODES = ('BNH', 'SSP')


class KeHoachSanXuat(models.Model):
    _name = 'ke.hoach.san.xuat'
    _description = 'Kế hoạch sản xuất theo tháng'
    _inherit = ['ke.hoach.line.mixin']

    _CHATTER_SCOPE = 'sx'
    _LINE_LABEL = 'kế hoạch sản xuất'

    company_sx_id = fields.Many2one(
        'res.company', string='Nhà máy SX', index=True,
        help='Đơn vị sản xuất (BNH/SSP) — gắn khi import hoặc tạo từ KD.',
    )

    _sql_constraints = [
        ('uniq_row',
         'unique(period_id, company_id, ma_sap)',
         'Trùng dòng: (Kỳ, Đơn vị, Mã) phải duy nhất!'),
    ]

    @api.model
    def _prepare_create_vals(self, vals_list):
        company = self.env.company
        for vals in vals_list:
            if not vals.get('company_id'):
                raise UserError(_(
                    'Đơn vị (SHI, TM2…) không được để trống trên kế hoạch sản xuất.'
                ))
            if (
                not vals.get('company_sx_id')
                and vals.get('period_id')
                and company.company_code in PRODUCTION_COMPANY_CODES
            ):
                vals['company_sx_id'] = company.id
