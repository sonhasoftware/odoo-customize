# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MaHangPhanTram(models.Model):
    _name = 'ma.hang.phan.tram'
    _description = 'Phần trăm dư mua theo mã NVL'
    _rec_name = 'ma_nvl_id'
    _order = 'company_id, ma_nvl_id'

    company_id = fields.Many2one(
        'res.company', string='Đơn vị', required=True, index=True, ondelete='cascade')
    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL', required=True, index=True, ondelete='restrict',
        domain="[('company_id', '=?', company_id)]",
    )
    ten_nvl = fields.Char(string='Tên NVL', related='ma_nvl_id.ten_hang', readonly=True)
    phan_tram = fields.Float(
        string='Phần trăm', digits=(16, 2), default=0.0,
        help='Hệ số mua dư so với nhu cầu tính toán, ví dụ 20 = mua thêm 20%.')

    _sql_constraints = [
        (
            'uniq_ma_hang_phan_tram_company_nvl',
            'unique(company_id, ma_nvl_id)',
            'Đã có phần trăm cho cùng Đơn vị và Mã NVL.',
        ),
    ]

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for rec in self:
            if rec.company_id and rec.ma_nvl_id and rec.ma_nvl_id.company_id != rec.company_id:
                rec.ma_nvl_id = False

    @api.onchange('ma_nvl_id')
    def _onchange_ma_nvl_id(self):
        for rec in self:
            if rec.ma_nvl_id and not rec.company_id and rec.ma_nvl_id.company_id:
                rec.company_id = rec.ma_nvl_id.company_id

    @api.constrains('company_id', 'ma_nvl_id')
    def _check_ma_nvl_company(self):
        for rec in self:
            if rec.ma_nvl_id and rec.company_id and rec.ma_nvl_id.company_id != rec.company_id:
                raise ValidationError(_(
                    'Mã NVL "%s" không thuộc đơn vị %s.'
                ) % (rec.ma_nvl_id.ma_sap, rec.company_id.display_name))

    @api.model
    def cron_clear_monthly(self):
        """Đầu tháng — reset cột phần trăm về 0, giữ nguyên danh mục mã NVL."""
        self.search([('phan_tram', '!=', 0.0)]).write({'phan_tram': 0.0})

    def action_open_import_wizard(self):
        return {
            'name': 'Import phần trăm',
            'type': 'ir.actions.act_window',
            'res_model': 'import.ma.hang.phan.tram.wizard',
            'view_mode': 'form',
            'target': 'new',
        }
