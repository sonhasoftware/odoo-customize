# -*- coding: utf-8 -*-
from odoo import fields, models


class MaHangPhanTram(models.Model):
    _name = 'ma.hang.phan.tram'
    _description = 'Phần trăm dư mua theo mã hàng'
    _rec_name = 'ma_sap'
    _order = 'company_id, ma_sap'

    company_id = fields.Many2one(
        'res.company', string='ĐVCS', required=True, index=True, ondelete='cascade')
    ma_sap = fields.Char(string='Mã NVL', required=True, index=True)
    phan_tram = fields.Float(
        string='Phần trăm', digits=(16, 2), default=0.0,
        help='Hệ số mua dư so với nhu cầu tính toán, ví dụ 20 = mua thêm 20%.')

    _sql_constraints = [
        (
            'uniq_ma_hang_phan_tram_company_sap',
            'unique(company_id, ma_sap)',
            'Đã có phần trăm cho cùng ĐVCS và Mã NVL.',
        ),
    ]
