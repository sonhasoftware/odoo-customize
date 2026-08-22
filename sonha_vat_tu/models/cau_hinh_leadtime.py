# -*- coding: utf-8 -*-
from odoo import api, fields, models


class CauHinhLeadtime(models.Model):
    """Master leadtime NVL — đồng bộ 2 chiều với B7 (phe.duyet.kh.vat.tu)."""
    _name = 'cau.hinh.leadtime'
    _description = 'Cấu hình leadtime vật tư'
    _rec_name = 'ma_nvl'
    _order = 'ma_nvl'

    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL', index=True, ondelete='restrict',
        help='Chọn từ danh mục ma.hang.',
    )
    ma_nvl = fields.Char(string='Mã NVL', required=True, index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    leadtime_ngay = fields.Integer(string='Leadtime (ngày)')

    _sql_constraints = [
        (
            'uniq_cau_hinh_leadtime_ma_nvl',
            'unique(ma_nvl)',
            'Đã có cấu hình leadtime cho mã NVL này.',
        ),
    ]

    @api.onchange('ma_nvl_id')
    def _onchange_ma_nvl_id(self):
        for rec in self:
            if rec.ma_nvl_id:
                rec.ma_nvl = (rec.ma_nvl_id.ma_sap or '').strip()
                rec.ten_nvl = rec.ma_nvl_id.ten_hang or ''

    @api.model
    def _apply_selection_to_vals(self, vals):
        vals = dict(vals)
        if vals.get('ma_nvl_id'):
            mh = self.env['ma.hang'].sudo().browse(vals['ma_nvl_id'])
            vals['ma_nvl'] = (mh.ma_sap or '').strip()
            if not vals.get('ten_nvl'):
                vals['ten_nvl'] = mh.ten_hang or ''
        if vals.get('ma_nvl'):
            vals['ma_nvl'] = str(vals['ma_nvl']).strip()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create([
            self._apply_selection_to_vals(vals) for vals in vals_list
        ])
        if not self.env.context.get('skip_phe_duyet_sync'):
            records._push_to_open_phe_duyet()
        return records

    def write(self, vals):
        if 'ma_nvl_id' in vals:
            vals = self._apply_selection_to_vals(vals)
        res = super().write(vals)
        if 'leadtime_ngay' in vals and not self.env.context.get('skip_phe_duyet_sync'):
            self._push_to_open_phe_duyet()
        return res

    @api.model
    def _find_ma_hang_nvl(self, ma_nvl):
        code = (ma_nvl or '').strip()
        if not code:
            return self.env['ma.hang']
        return self.env['ma.hang'].sudo().search(
            [('ma_sap', '=', code)], order='id', limit=1,
        )

    @api.model
    def _upsert_from_phe_duyet(self, line):
        ma = (line.ma_sap or '').strip()
        if not ma:
            return
        sync_ctx = {'skip_phe_duyet_sync': True}
        nvl_mh = self._find_ma_hang_nvl(ma)
        vals = {
            'ma_nvl': ma,
            'ten_nvl': line.ten_nvl or (nvl_mh.ten_hang if nvl_mh else ''),
            'leadtime_ngay': line.leadtime_ngay or 0,
            'ma_nvl_id': nvl_mh.id if nvl_mh else False,
        }
        existing = self.search([('ma_nvl', '=', ma)], limit=1)
        if existing:
            existing.with_context(**sync_ctx).write(vals)
        else:
            self.with_context(**sync_ctx).create(vals)

    def _push_to_open_phe_duyet(self):
        PheDuyet = self.env['phe.duyet.kh.vat.tu']
        for rec in self:
            ma = (rec.ma_nvl or '').strip()
            if not ma:
                continue
            lines = PheDuyet.search([
                ('ma_sap', '=', ma),
                ('period_id.state', '=', 'phe_duyet'),
            ])
            if lines:
                lines.with_context(skip_leadtime_sync=True).write({
                    'leadtime_ngay': rec.leadtime_ngay or 0,
                })
