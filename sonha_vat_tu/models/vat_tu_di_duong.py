# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VatTuDiDuong(models.Model):
    _name = 'vat.tu.di.duong'
    _description = 'Vật tư đi đường (BCU)'
    _order = 'company_id, month_key, ma_sap'

    company_id = fields.Many2one(
        'res.company',
        string='Đơn vị',
        default=lambda self: self.env.company,
        index=True,
        help='Để trống = dùng chung mọi công ty (ví dụ dữ liệu demo).',
    )
    ma_sap = fields.Char(string='Mã SAP', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    so_luong = fields.Float(string='Số lượng', digits=(16, 3))

    _sql_constraints = [
        ('uniq_company_sap_month',
         'unique(company_id, ma_sap, month_key)',
         'Đã có dòng vật tư đi đường cho cùng Đơn vị, Mã SAP và Tháng.'),
    ]

    @api.constrains('month_key')
    def _check_month_key(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.month_key and not pattern.match(rec.month_key):
                raise ValidationError(
                    'Tháng phải đúng định dạng MM/YYYY, ví dụ 04/2026.'
                )

