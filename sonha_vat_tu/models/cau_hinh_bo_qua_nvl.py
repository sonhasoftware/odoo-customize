# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CauHinhBoQuaNvl(models.Model):
    """Mã NVL không mua — B2 lấy mã cha (BTP) trên cây BOM thay cho lá bị bỏ qua."""
    _name = 'cau.hinh.bo.qua.nvl'
    _description = 'Cấu hình bỏ qua mã NVL (lấy mã cha BOM)'
    _rec_name = 'ma_nvl_id'
    _order = 'company_sx_id, ma_nvl_id'

    company_sx_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất', required=True,
        index=True, ondelete='cascade',
        context={'vat_tu_company_code_display': True},
    )
    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL', required=True,
        index=True, ondelete='restrict'
    )
    ma_nvl = fields.Char(
        string='Mã NVL', related='ma_nvl_id.ma_sap', store=True, readonly=True,
    )
    ten_nvl = fields.Char(
        string='Tên NVL', related='ma_nvl_id.ten_hang', store=True, readonly=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'uniq_cau_hinh_bo_qua_nvl_sx_ma',
            'unique(company_sx_id, ma_nvl_id)',
            'Đã có cấu hình bỏ qua cho cùng ĐV SX và mã NVL.',
        ),
    ]

    @api.onchange('company_sx_id')
    def _onchange_company_sx_id(self):
        for rec in self:
            if rec.company_sx_id and rec.ma_nvl_id and rec.ma_nvl_id.company_id != rec.company_sx_id:
                rec.ma_nvl_id = False
