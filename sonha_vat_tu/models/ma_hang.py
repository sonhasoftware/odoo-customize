# -*- coding: utf-8 -*-
from odoo import fields, models


class MaHang(models.Model):
    _name = 'ma.hang'
    _description = 'Danh mục mã hàng'
    _rec_name = 'code'
    _order = 'code, ma_sap'

    code = fields.Char(string='Mã hàng', index=True)
    ma_sap = fields.Char(string='Mã SAP', index=True)
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    nganh_hang_id = fields.Many2one(
        'nganh.hang',
        string='Ngành hàng',
        related='dong_hang_id.nganh_hang_id',
        store=True,
        readonly=True,
        index=True)
    dong_hang_id = fields.Many2one(
        'dong.hang', string='Dòng hàng', ondelete='restrict', index=True)
    don_vi_tinh_id = fields.Many2one('uom.uom', string='Đơn vị tính')

    _sql_constraints = [
        ('vtc_ma_hang_code_uniq', 'unique(code)', 'Mã hàng phải duy nhất!'),
        ('vtc_ma_hang_sap_uniq', 'unique(ma_sap)', 'Mã SAP phải duy nhất!'),
        ('vtc_ma_hang_nvl_uniq', 'unique(ma_nvl)', 'Mã NVL phải duy nhất!'),
    ]
