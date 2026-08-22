# -*- coding: utf-8 -*-
from odoo import fields, models


class DmtbNhom(models.Model):
    _name = 'dmtb.nhom'
    _description = 'Nhóm ngành hàng — báo cáo định mức vật tư trung bình'
    _order = 'name, id'

    name = fields.Char(string='Tên nhóm', required=True, index=True)
    active = fields.Boolean(default=True)
    nganh_hang_ids = fields.Many2many(
        'mdm.nganh.hang',
        'dmtb_nhom_nganh_hang_rel',
        'nhom_id',
        'nganh_hang_id',
        string='Ngành hàng',
    )

    _sql_constraints = [
        ('uniq_dmtb_nhom_name', 'unique(name)', 'Tên nhóm phải duy nhất.'),
    ]
