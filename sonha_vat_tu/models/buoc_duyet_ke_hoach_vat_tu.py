# -*- coding: utf-8 -*-
from odoo import fields, models


class BuocDuyetKeHoachVatTu(models.Model):
    _name = 'buoc.duyet.ke.hoach.vat.tu'
    _description = 'Bước duyệt kế hoạch vật tư'
    _order = 'sequence, id'

    sequence = fields.Integer(string='STT', required=True, default=1, index=True)
    phuong_thuc = fields.Selection(
        [('ql', 'Quản lý trực tiếp'), ('vt', 'Vai trò')],
        string='Phương thức',
        required=True,
    )
    vai_tro_id = fields.Many2one('vai.tro', string='Vai trò', ondelete='restrict')
    nguoi_duyet_id = fields.Many2one(
        'res.users',
        string='Người duyệt',
        required=True,
        ondelete='restrict',
        index=True,
    )
    da_duyet = fields.Boolean(string='Đã duyệt', default=False, readonly=True)
    ngay_duyet = fields.Datetime(string='Ngày duyệt', readonly=True)
    period_id = fields.Many2one(
        'ke.hoach.vat.tu',
        string='Kế hoạch vật tư',
        required=True,
        ondelete='cascade',
        index=True,
    )
