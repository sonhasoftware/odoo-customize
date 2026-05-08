# -*- coding: utf-8 -*-
from odoo import fields, models


class NganhHang(models.Model):
    _name = 'nganh.hang'
    _table = 'vtc_nganh_hang'
    _description = 'Danh mục ngành hàng B1'
    _rec_name = 'name'
    _order = 'code, name'

    code = fields.Char(string='Mã', index=True)
    name = fields.Char(string='Ngành hàng', index=True)

    _sql_constraints = [
        ('vtc_nganh_hang_code_uniq', 'unique(code)', 'Mã ngành hàng phải duy nhất!'),
    ]
