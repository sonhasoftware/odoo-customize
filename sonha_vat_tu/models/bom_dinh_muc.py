# -*- coding: utf-8 -*-
from odoo import api, fields, models


class BomDinhMuc(models.Model):
    """Master định mức thay đổi."""
    _name = 'bom.dinh.muc'
    _description = 'BOM định mức thay đổi'
    _rec_name = 'ma_tp'
    _order = 'company_id, ma_tp, ma_nvl'

    company_id = fields.Many2one(
        'res.company', string='Đơn vị', required=True, index=True, ondelete='cascade')
    ma_tp_line_id = fields.Many2one(
        'mdm.tong.hop.line', string='Mã thành phẩm', index=True, ondelete='restrict',
        domain="[('dvcs', '=?', company_id)]",
        help='Thành phẩm — chọn từ MDM (mdm.tong.hop.line), cùng nguồn import kế hoạch.',
    )
    ma_tp = fields.Char(string='Mã thành phẩm', required=True, index=True)
    ten_tp = fields.Char(string='Tên thành phẩm')
    ma_nvl_id = fields.Many2one(
        'ma.hang', string='Mã NVL', index=True, ondelete='restrict',
        domain="[('company_id', '=?', company_id)]",
        help='NVL cuối — chọn từ danh mục ma.hang.',
    )
    ma_nvl = fields.Char(string='Mã NVL', required=True, index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    sl_dinh_muc = fields.Float(
        string='Định mức', digits=(16, 3), readonly=True,
        help='Định mức gốc từ BOM — cập nhật khi đồng bộ từ B2.',
    )
    sl_dinh_muc_thay_doi = fields.Float(
        string='Định mức thay đổi', digits=(16, 3),
        help='Để trống = dùng định mức gốc. Có giá trị = áp dụng thay cho định mức gốc.',
    )

    _sql_constraints = [
        (
            'uniq_bom_dinh_muc_company_tp_nvl',
            'unique(company_id, ma_tp, ma_nvl)',
            'Đã có dòng BOM cho cùng Đơn vị, Mã thành phẩm và Mã NVL.',
        ),
    ]

    @api.onchange('company_id')
    def _onchange_company_id(self):
        for rec in self:
            if not rec.company_id:
                continue
            if rec.ma_tp_line_id and rec.ma_tp_line_id.dvcs != rec.company_id:
                rec.ma_tp_line_id = False
            if rec.ma_nvl_id and rec.ma_nvl_id.company_id != rec.company_id:
                rec.ma_nvl_id = False

    @api.onchange('ma_tp_line_id')
    def _onchange_ma_tp_line_id(self):
        for rec in self:
            if rec.ma_tp_line_id:
                rec.ma_tp = (rec.ma_tp_line_id.ma_dv or '').strip()
                rec.ten_tp = rec.ma_tp_line_id.ten or ''
                if not rec.company_id and rec.ma_tp_line_id.dvcs:
                    rec.company_id = rec.ma_tp_line_id.dvcs

    @api.onchange('ma_nvl_id')
    def _onchange_ma_nvl_id(self):
        for rec in self:
            if rec.ma_nvl_id:
                rec.ma_nvl = (rec.ma_nvl_id.ma_sap or '').strip()
                rec.ten_nvl = rec.ma_nvl_id.ten_hang or ''
                if not rec.company_id and rec.ma_nvl_id.company_id:
                    rec.company_id = rec.ma_nvl_id.company_id

    @api.model
    def _find_mdm_tp_line(self, company_id, ma_tp):
        code = (ma_tp or '').strip()
        if not code:
            return self.env['mdm.tong.hop.line']
        MdmLine = self.env['mdm.tong.hop.line'].sudo()
        if company_id:
            line = MdmLine.search([('ma_dv', '=', code), ('dvcs', '=', company_id)], limit=1)
            if line:
                return line
        return MdmLine.search([('ma_dv', '=', code)], limit=1)

    @api.model
    def _find_ma_hang_nvl(self, company_id, ma_nvl):
        code = (ma_nvl or '').strip()
        if not code:
            return self.env['ma.hang']
        MaHang = self.env['ma.hang'].sudo()
        recs = MaHang.search([('ma_sap', '=', code)], order='company_id, id')
        if not recs:
            return MaHang
        if company_id:
            matched = recs.filtered(lambda r: r.company_id.id == company_id)
            if matched:
                return matched[0]
        return recs[0]

    @api.model
    def _apply_selection_to_vals(self, vals):
        vals = dict(vals)
        if vals.get('ma_tp_line_id'):
            line = self.env['mdm.tong.hop.line'].sudo().browse(vals['ma_tp_line_id'])
            vals['ma_tp'] = (line.ma_dv or '').strip()
            vals['ten_tp'] = line.ten or ''
        if vals.get('ma_nvl_id'):
            mh = self.env['ma.hang'].sudo().browse(vals['ma_nvl_id'])
            vals['ma_nvl'] = (mh.ma_sap or '').strip()
            vals['ten_nvl'] = mh.ten_hang or ''
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([
            self._apply_selection_to_vals(vals) for vals in vals_list
        ])

    def write(self, vals):
        if {'ma_tp_line_id', 'ma_nvl_id'} & set(vals):
            vals = self._apply_selection_to_vals(vals)
        res = super().write(vals)
        if 'sl_dinh_muc_thay_doi' in vals and not self.env.context.get('skip_dinh_muc_sync'):
            self._push_to_open_periods()
        return res

    @api.model
    def _upsert_from_dinh_muc(self, line, update_override=True):
        """Ghi master từ dòng định mức kỳ — cùng khóa char với B2."""
        ma_tp = (line.ma_sap or '').strip()
        ma_nvl = (line.ma_nvl or '').strip()
        if not line.company_id or not ma_tp or not ma_nvl:
            return
        tp_line = self._find_mdm_tp_line(line.company_id.id, ma_tp)
        nvl_mh = self._find_ma_hang_nvl(line.company_id.id, ma_nvl)
        sync_ctx = {'skip_dinh_muc_sync': True}
        vals = {
            'company_id': line.company_id.id,
            'ma_tp_line_id': tp_line.id if tp_line else False,
            'ma_tp': ma_tp,
            'ten_tp': line.ten_sap or (tp_line.ten if tp_line else ''),
            'ma_nvl_id': nvl_mh.id if nvl_mh else False,
            'ma_nvl': ma_nvl,
            'ten_nvl': line.ten_nvl or (nvl_mh.ten_hang if nvl_mh else ''),
            'sl_dinh_muc': line.sl_dinh_muc or 0.0,
        }
        if update_override:
            if line.co_sl_dinh_muc_override:
                vals['sl_dinh_muc_thay_doi'] = line.sl_dinh_muc_thay_doi or 0.0
            else:
                vals['sl_dinh_muc_thay_doi'] = 0.0
        existing = self.search([
            ('company_id', '=', line.company_id.id),
            ('ma_tp', '=', ma_tp),
            ('ma_nvl', '=', ma_nvl),
        ], limit=1)
        if existing:
            write_vals = dict(vals)
            if not update_override:
                write_vals.pop('sl_dinh_muc_thay_doi', None)
            existing.with_context(**sync_ctx).write(write_vals)
        else:
            if not update_override:
                vals.pop('sl_dinh_muc_thay_doi', None)
            self.with_context(**sync_ctx).create(vals)

    def _push_to_open_periods(self):
        DinhMuc = self.env['dinh.muc']
        for rec in self:
            if not rec.company_id or not rec.ma_tp or not rec.ma_nvl:
                continue
            lines = DinhMuc.search([
                ('company_id', '=', rec.company_id.id),
                ('ma_sap', '=', rec.ma_tp),
                ('ma_nvl', '=', rec.ma_nvl),
                ('period_id.state', '=', 'dinh_muc'),
            ])
            if lines:
                lines.with_context(skip_bom_dinh_muc_sync=True)._apply_master_override(rec)
