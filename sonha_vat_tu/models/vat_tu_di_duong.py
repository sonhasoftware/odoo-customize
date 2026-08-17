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
        string='Đơn vị sản xuất',
        default=lambda self: self._default_company_id(),
        index=True,
        help='Nhà máy sản xuất (BNH, SSP…) — cùng Đơn vị SX trên kỳ KHVT.',
    )
    loai = fields.Selection(
        [
            (LOAI_DON_VI, 'SX (B3)'),
            (LOAI_BCU, 'BCU (B6)'),
        ],
        string='Loại',
        default=LOAI_DON_VI,
        required=True,
        index=True,
        help='SX: import tại bước Tính toán vật tư. BCU: import tại Tổng hợp BCU.',
    )
    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL (MDM)', index=True, ondelete='restrict',
    )
    ma_nvl = fields.Char(string='Mã NVL', required=True, index=True)
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
            'Đã có dòng vật tư đi đường cho cùng Đơn vị sản xuất, Mã NVL, Tháng và Loại.',
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
    def _default_company_id(self):
        period_id = self.env.context.get('default_period_id')
        if period_id:
            period = self.env['ke.hoach.vat.tu'].browse(period_id)
            if period.company_sx_id:
                return period.company_sx_id.id
        loai = self._loai_from_context()
        if loai == self.LOAI_BCU:
            period = self.env['ke.hoach.vat.tu'].search([
                ('state', 'in', ('dat_hang', 'bcu_tong_hop', 'phe_duyet')),
                ('company_sx_id', '!=', False),
            ], order='id desc', limit=1)
            if period.company_sx_id:
                return period.company_sx_id.id
        return self.env.company.id

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

    @api.model
    def _apply_ma_nvl_vals(self, vals, ten_nvl_map=None):
        """Chỉ lưu mã/text NVL — company_id là ĐV SX, không gắn FK ma.hang (ĐVCS)."""
        vals = dict(vals)
        if vals.get('ma_nvl'):
            vals['ma_nvl'] = str(vals['ma_nvl']).strip()
            if not vals.get('ten_nvl'):
                if ten_nvl_map is not None:
                    vals['ten_nvl'] = ten_nvl_map.get(vals['ma_nvl']) or False
                else:
                    vals['ten_nvl'] = self._ten_nvl_map([vals['ma_nvl']]).get(vals['ma_nvl']) or False
        vals.pop('ma_nvl_id', None)
        return vals

    @api.model
    def _prepare_import_vals_list(self, vals_list):
        if not vals_list:
            return []
        loai = vals_list[0].get('loai') or self.env.context.get('vat_tu_di_duong_loai') or self.LOAI_DON_VI
        codes = sorted({
            str(vals.get('ma_nvl') or '').strip()
            for vals in vals_list if (vals.get('ma_nvl') or '').strip()
        })
        ten_nvl_map = self._ten_nvl_map(codes) if codes else {}
        Period = self.env['ke.hoach.vat.tu']
        prepared = []
        for vals in vals_list:
            vals = self._apply_ma_nvl_vals(vals, ten_nvl_map=ten_nvl_map)
            vals.setdefault('loai', loai)
            if vals.get('month_key') and not vals.get('month_date'):
                vals['month_date'] = Period._month_key_to_date(vals['month_key'])
            prepared.append(vals)
        return prepared

    @api.model
    def _bulk_create_import_rows(self, vals_list):
        """Ghi nhanh từ wizard import — tránh ORM create từng dòng."""
        if not vals_list:
            return self.browse()
        allowed = self._allowed_loai_for_user()
        prepared = self._prepare_import_vals_list(vals_list)
        for vals in prepared:
            if vals['loai'] not in allowed:
                self._check_loai_access([vals['loai']])

        company_ids, loais, ma_nvls, ten_nvls = [], [], [], []
        month_keys, month_dates, so_luongs = [], [], []
        for vals in prepared:
            company_ids.append(vals['company_id'])
            loais.append(vals['loai'])
            ma_nvls.append(vals.get('ma_nvl') or '')
            ten_nvls.append(vals.get('ten_nvl') or False)
            month_keys.append(vals['month_key'])
            month_dates.append(vals['month_date'])
            so_luongs.append(vals.get('so_luong') or 0.0)

        self.env.cr.execute("""
            INSERT INTO vat_tu_di_duong (
                company_id, loai, ma_nvl, ten_nvl,
                month_key, month_date, so_luong, don_gia, gia_tri,
                create_uid, write_uid, create_date, write_date
            )
            SELECT
                v.company_id, v.loai, v.ma_nvl, v.ten_nvl,
                v.month_key, v.month_date, v.so_luong,
                0, COALESCE(v.so_luong, 0) * 0,
                %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
            FROM unnest(
                %s::int[], %s::varchar[], %s::varchar[], %s::varchar[],
                %s::varchar[], %s::date[], %s::numeric[]
            ) AS v(
                company_id, loai, ma_nvl, ten_nvl,
                month_key, month_date, so_luong
            )
            RETURNING id
        """, [
            self.env.uid, self.env.uid,
            company_ids, loais, ma_nvls, ten_nvls,
            month_keys, month_dates, so_luongs,
        ])
        new_ids = [row[0] for row in self.env.cr.fetchall()]
        records = self.browse(new_ids)
        records.invalidate_recordset()
        return records

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
        if self.env.context.get('vat_tu_import_bulk'):
            return self._bulk_create_import_rows(vals_list)

        Period = self.env['ke.hoach.vat.tu']
        allowed = self._allowed_loai_for_user()
        default_loai = self._loai_from_context()
        codes = sorted({
            str(vals.get('ma_nvl') or '').strip()
            for vals in vals_list if (vals.get('ma_nvl') or '').strip()
        })
        ten_nvl_map = self._ten_nvl_map(codes) if codes else {}
        prepared = []
        for vals in vals_list:
            vals = self._apply_ma_nvl_vals(vals, ten_nvl_map=ten_nvl_map)
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
        if {'ma_nvl', 'ten_nvl'} & set(vals):
            vals = self._apply_ma_nvl_vals(vals)
        return super().write(vals)

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
