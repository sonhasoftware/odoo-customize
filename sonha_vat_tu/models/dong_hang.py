# -*- coding: utf-8 -*-
from odoo import fields, models


class DongHang(models.Model):
    _name = 'dong.hang'
    _description = 'Danh mục dòng hàng'
    _rec_name = 'name'
    _order = 'code, name'

    code = fields.Char(string='Mã', index=True)
    name = fields.Char(string='Dòng hàng', index=True)
    nganh_hang_id = fields.Many2one(
        'nganh.hang', string='Ngành hàng', ondelete='restrict', index=True)
