# -*- coding: utf-8 -*-
import re

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class KeHoachKinhDoanh(models.Model):
    """Chứng từ kế hoạch kinh doanh (header) — một file Excel import = một bản ghi."""
    _name = 'ke.hoach.kinh.doanh'
    _description = 'Kế hoạch kinh doanh'
    _rec_name = 'code'
    _order = 'period_month desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    code = fields.Char(
        string='Số chứng từ', readonly=True, copy=False, index=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Đơn vị đặt hàng',
        required=True, index=True, tracking=True,
        help='Đơn vị kinh doanh / đặt hàng của gói import (SHI, NAN…).',
    )
    period_month = fields.Char(string='Tháng bắt đầu', required=True, tracking=True)
    company_sx_id = fields.Many2one(
        'res.company', string='Đơn vị sản xuất',
        required=True, index=True, readonly=True, tracking=True,
        default=lambda self: self.env.company.id,
        help='Nhà máy sản xuất (BNH, SSP…) — lấy theo công ty đang đăng nhập.',
    )
    locked = fields.Boolean(
        string='Đã lấy vào SX',
        default=False, copy=False, readonly=True,
        help='Khóa khi đã lấy vào kế hoạch sản xuất; không sửa/import lại.',
    )
    period_sx_id = fields.Many2one(
        'ke.hoach.vat.tu', string='Kỳ SX đã lấy',
        readonly=True, copy=False, index=True, ondelete='set null',
    )
    line_ids = fields.One2many(
        'ke.hoach.kinh.doanh.line', 'kinh_doanh_id', string='Chi tiết kế hoạch')
    co_ke_hoach_vat_tu = fields.Boolean(
        string='Đã có kế hoạch vật tư',
        compute='_compute_co_ke_hoach_vat_tu',
    )

    @api.depends('period_sx_id', 'period_sx_id.co_ke_hoach_vat_tu')
    def _compute_co_ke_hoach_vat_tu(self):
        for rec in self:
            rec.co_ke_hoach_vat_tu = bool(
                rec.period_sx_id and rec.period_sx_id.co_ke_hoach_vat_tu
            )

    @api.constrains('period_month')
    def _check_period_month(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.period_month and not pattern.match(rec.period_month.strip()):
                raise ValidationError(
                    _('Tháng bắt đầu phải có dạng MM/YYYY (vd. 07/2026).'))

    @api.model
    def _company_code(self, company=None):
        company = company or self.env.company
        code = (getattr(company, 'company_code', None) or '').strip()
        return code or (company.name or 'XX').strip()

    @api.model
    def _code_prefix(self, period_month, company_code=None):
        company_code = (company_code or self._company_code()).strip()
        month, year = period_month.split('/')
        return 'KHKD_%s_%s%s' % (company_code, month, year)

    @api.model
    def _next_code(self, period_month, company_code=None):
        prefix = self._code_prefix(period_month, company_code) + '_'
        latest = self.sudo().search(
            [('code', '=like', prefix + '%')], order='code desc', limit=1)
        next_no = 1
        if latest.code:
            try:
                next_no = int(latest.code.rsplit('_', 1)[-1]) + 1
            except (TypeError, ValueError):
                next_no = 1
        return '%s%02d' % (prefix, next_no)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('company_sx_id'):
                vals['company_sx_id'] = self.env.company.id
            if not vals.get('code') and vals.get('period_month') and vals.get('company_id'):
                company = self.env['res.company'].browse(vals['company_id'])
                vals['code'] = self._next_code(
                    vals['period_month'],
                    self._company_code(company),
                )
        return super().create(vals_list)

    def write(self, vals):
        if vals.keys() - {'locked', 'period_sx_id', 'code'}:
            self._check_editable()
        vals.pop('company_sx_id', None)
        res = super().write(vals)
        if not self.env.context.get('skip_kd_code_update'):
            for rec in self.filtered(lambda r: not r.code and r.period_month and r.company_id):
                rec.with_context(skip_kd_code_update=True).write({
                    'code': self._next_code(
                        rec.period_month,
                        self._company_code(rec.company_id),
                    ),
                })
        return res

    def _get_horizon_months(self):
        return self.env['ke.hoach.vat.tu'].new(
            {'period_month': self.period_month}
        )._get_horizon_months()

    def _check_editable(self):
        locked = self.filtered('locked')
        if locked:
            raise UserError(_(
                'Kế hoạch kinh doanh đã lấy vào sản xuất, không thể sửa.'
            ))

    def unlink(self):
        self._check_editable()
        return super().unlink()

    def _has_edit_rights(self):
        return (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu')
            or self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        )

    def action_download_template(self):
        self.ensure_one()
        self._check_editable()
        if not self.company_sx_id:
            raise UserError(_('Đơn vị sản xuất không được để trống.'))
        if not self._has_edit_rights():
            raise UserError(_('Bạn không có quyền tải template kế hoạch kinh doanh.'))
        return self.env['ke.hoach.vat.tu']._download_kinh_doanh_template(self)

    def action_open_import_wizard(self):
        self.ensure_one()
        self._check_editable()
        if not self._has_edit_rights():
            raise UserError(_('Bạn không có quyền import kế hoạch kinh doanh.'))
        return {
            'name': _('Import kế hoạch kinh doanh'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ke.hoach.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_kinh_doanh_id': self.id,
                'default_import_type': 'business',
            },
        }

    def name_get(self):
        result = []
        for rec in self:
            company = rec.company_id.company_code or rec.company_id.name or ''
            sx = rec.company_sx_id.company_code or rec.company_sx_id.name or ''
            name = '%s · %s · %s · %d dòng' % (
                company, rec.period_month or '', sx, len(rec.line_ids))
            result.append((rec.id, name))
        return result
