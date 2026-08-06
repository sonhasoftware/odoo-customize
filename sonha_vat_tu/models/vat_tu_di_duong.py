# -*- coding: utf-8 -*-
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class VatTuDiDuong(models.Model):
    _name = 'vat.tu.di.duong'
    _description = 'Vật tư đi đường'
    _order = 'company_id, loai, month_date, ma_nvl'

    LOAI_DON_VI = 'don_vi'
    LOAI_BCU = 'bcu'

    company_id = fields.Many2one(
        'res.company',
        string='Đơn vị',
        default=lambda self: self.env.company,
        index=True,
        help='Đơn vị nhận vật tư đi đường.',
    )
    loai = fields.Selection(
        [
            (LOAI_DON_VI, 'Đơn vị KD'),
            (LOAI_BCU, 'BCU'),
        ],
        string='Loại',
        default=LOAI_DON_VI,
        required=True,
        index=True,
        help='Đơn vị KD: import từ SX (B3). BCU: import tại bước tổng hợp BCU (B6).',
    )
    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL', index=True, ondelete='restrict',
        domain="[('company_id', '=?', company_id)]",
    )
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL', index=True)
    month_key = fields.Char(string='Tháng', index=True)
    month_date = fields.Date(string='Tháng tính toán', index=True)
    so_luong = fields.Float(string='Số lượng', digits=(16, 3))
    don_gia = fields.Float(string='Đơn giá', digits=(16, 2))
    gia_tri = fields.Float(
        string='Giá trị',
        compute='_compute_gia_tri',
        store=True,
        digits=(16, 2),
    )

    _sql_constraints = [
        (
            'uniq_vdd_company_nvl_month_loai',
            'unique(company_id, ma_nvl, month_key, loai)',
            'Đã có dòng vật tư đi đường cho cùng Đơn vị, Mã NVL, Tháng và Loại.',
        ),
    ]

    @api.depends('so_luong', 'don_gia')
    def _compute_gia_tri(self):
        for rec in self:
            rec.gia_tri = (rec.so_luong or 0.0) * (rec.don_gia or 0.0)

    @api.model
    def _is_bcu_user(self):
        return self.env.user.has_group('sonha_vat_tu.group_ban_cung_ung_vat_tu')

    @api.model
    def _is_sx_user(self):
        return (
            self.env.user.has_group('sonha_vat_tu.group_bo_phan_vat_tu')
            or self.env.user.has_group('sonha_vat_tu.group_truong_bo_phan_vat_tu')
        )

    @api.model
    def _loai_from_context(self):
        ctx_loai = self.env.context.get('default_loai') or self.env.context.get('vat_tu_di_duong_loai')
        if ctx_loai in (self.LOAI_DON_VI, self.LOAI_BCU):
            return ctx_loai
        if self._is_bcu_user() and not self._is_sx_user():
            return self.LOAI_BCU
        return self.LOAI_DON_VI

    @api.model
    def _allowed_loai_for_user(self):
        if self._is_bcu_user() and not self._is_sx_user():
            return {self.LOAI_BCU}
        if self._is_sx_user() and not self._is_bcu_user():
            return {self.LOAI_DON_VI}
        if self._is_bcu_user():
            return {self.LOAI_BCU}
        return {self.LOAI_DON_VI}

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'loai' in fields_list and not res.get('loai'):
            res['loai'] = self._loai_from_context()
        return res

    def _check_loai_access(self, loai_values=None):
        allowed = self._allowed_loai_for_user()
        if self.env.su:
            return
        targets = loai_values if loai_values is not None else self.mapped('loai')
        for loai in targets:
            if loai not in allowed:
                label = dict(self._fields['loai'].selection).get(loai, loai)
                raise AccessError(
                    _('Bạn không có quyền thao tác vật tư đi đường loại "%s".') % label
                )

    @api.model
    def _ten_nvl_map(self, codes):
        codes = [code for code in set(codes) if code]
        if not codes:
            return {}
        return {
            rec.ma_sap: rec.ten_hang
            for rec in self.env['ma.hang'].search([('ma_sap', 'in', codes)])
        }

    def _get_ten_nvl(self, ma_nvl):
        return self._ten_nvl_map([ma_nvl]).get(ma_nvl) or False

    @api.model
    def _find_ma_hang_nvl(self, company_id, ma_nvl):
        code = (ma_nvl or '').strip()
        if not code:
            return self.env['ma.hang']
        domain = [('ma_sap', '=', code)]
        if company_id:
            mh = self.env['ma.hang'].sudo().search(
                domain + [('company_id', '=', company_id)], limit=1,
            )
            if mh:
                return mh
        return self.env['ma.hang'].sudo().search(domain, limit=1)

    @api.model
    def _apply_ma_nvl_vals(self, vals, company_id=None):
        vals = dict(vals)
        cid = company_id or vals.get('company_id')
        if vals.get('ma_nvl_id'):
            mh = self.env['ma.hang'].sudo().browse(vals['ma_nvl_id'])
            vals['ma_nvl'] = (mh.ma_sap or '').strip()
            vals['ten_nvl'] = mh.ten_hang or ''
        elif vals.get('ma_nvl'):
            vals['ma_nvl'] = str(vals['ma_nvl']).strip()
            if not vals.get('ten_nvl'):
                vals['ten_nvl'] = self._get_ten_nvl(vals['ma_nvl']) or False
            if not vals.get('ma_nvl_id'):
                mh = self._find_ma_hang_nvl(cid, vals['ma_nvl'])
                if mh:
                    vals['ma_nvl_id'] = mh.id
        return vals

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for rec in self:
            if (
                rec.company_id and rec.ma_nvl_id
                and rec.ma_nvl_id.company_id
                and rec.ma_nvl_id.company_id != rec.company_id
            ):
                rec.ma_nvl_id = False
                rec.ma_nvl = False
                rec.ten_nvl = False

    @api.onchange('ma_nvl_id')
    def _onchange_ma_nvl_id(self):
        for rec in self:
            if rec.ma_nvl_id:
                rec.ma_nvl = (rec.ma_nvl_id.ma_sap or '').strip()
                rec.ten_nvl = rec.ma_nvl_id.ten_hang or ''
                if not rec.company_id and rec.ma_nvl_id.company_id:
                    rec.company_id = rec.ma_nvl_id.company_id

    @api.constrains('company_id', 'ma_nvl_id')
    def _check_ma_nvl_company(self):
        for rec in self:
            if (
                rec.ma_nvl_id and rec.company_id
                and rec.ma_nvl_id.company_id
                and rec.ma_nvl_id.company_id != rec.company_id
            ):
                raise ValidationError(_(
                    'Mã NVL "%s" không thuộc đơn vị %s.',
                ) % (rec.ma_nvl_id.ma_sap, rec.company_id.display_name))

    @api.constrains('month_key')
    def _check_month_key(self):
        pattern = re.compile(r'^(0[1-9]|1[0-2])/\d{4}$')
        for rec in self:
            if rec.month_key and not pattern.match(rec.month_key):
                raise ValidationError('Tháng phải đúng định dạng MM/YYYY, ví dụ 04/2026.')

    @api.constrains('loai')
    def _check_loai_value(self):
        self._check_loai_access()

    @api.model_create_multi
    def create(self, vals_list):
        Period = self.env['ke.hoach.vat.tu']
        allowed = self._allowed_loai_for_user()
        default_loai = self._loai_from_context()
        prepared = []
        for vals in vals_list:
            vals = self._apply_ma_nvl_vals(vals)
            vals.setdefault('loai', default_loai)
            if vals['loai'] not in allowed:
                self._check_loai_access([vals['loai']])
            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if 'loai' in vals:
            self._check_loai_access([vals['loai']])
        elif not self.env.su:
            self._check_loai_access()
        vals = dict(vals)
        if 'month_key' in vals:
            vals['month_date'] = self.env['ke.hoach.vat.tu']._month_key_to_date(vals.get('month_key'))
        if {'ma_nvl_id', 'ma_nvl', 'company_id'} & set(vals):
            company_id = vals.get('company_id')
            if company_id is None and len(self) == 1:
                company_id = self.company_id.id
            vals = self._apply_ma_nvl_vals(vals, company_id=company_id)
        return super().write(vals)

    def init(self):
        super().init()
        self.env.cr.execute(
            """
            UPDATE vat_tu_di_duong v
            SET ma_nvl_id = sub.ma_hang_id
            FROM (
                SELECT DISTINCT ON (v2.id)
                    v2.id AS vdd_id,
                    mh.id AS ma_hang_id
                FROM vat_tu_di_duong v2
                JOIN ma_hang mh ON TRIM(mh.ma_sap) = TRIM(v2.ma_nvl)
                WHERE v2.ma_nvl_id IS NULL
                  AND v2.ma_nvl IS NOT NULL
                  AND TRIM(v2.ma_nvl) <> ''
                ORDER BY v2.id,
                    CASE WHEN v2.company_id = mh.company_id THEN 0 ELSE 1 END,
                    mh.id
            ) sub
            WHERE v.id = sub.vdd_id
            """
        )

    def action_open_import_wizard(self):
        loai = self._loai_from_context()
        if loai == self.LOAI_BCU:
            return self.env['import.tong.hop.bcu.wizard'].action_open_from_menu()
        return {
            'name': _('Import vật tư đi đường'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.vat.tu.di.duong.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_loai': self.LOAI_DON_VI,
                'vat_tu_di_duong_loai': self.LOAI_DON_VI,
            },
        }
