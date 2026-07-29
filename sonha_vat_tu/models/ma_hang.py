# -*- coding: utf-8 -*-
import logging
import os as _os

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class MaHang(models.Model):
    _name = 'ma.hang'
    _description = 'Danh mục mã hàng'
    _auto = False
    _rec_name = 'ma_sap'
    _order = 'ma_sap'

    mdm_line_id = fields.Many2one(
        'mdm.tong.hop.line', string='Dòng MDM', readonly=True, index=True)
    mdm_id = fields.Many2one(
        'mdm.tong.hop', string='Hàng hóa MDM', readonly=True, index=True)
    ma_mdm = fields.Char(string='Mã MDM', readonly=True, index=True)
    ma_sap = fields.Char(string='Mã đơn vị', readonly=True, index=True)
    ten_hang = fields.Char(string='Tên hàng hóa', readonly=True)
    phan_tram = fields.Float(
        string='Phần trăm', digits=(16, 2), compute='_compute_phan_tram',
        help='Hệ số mua dư so với nhu cầu tính toán (áp dụng ở B4).')
    don_vi_tinh_id = fields.Many2one(
        'mdm.dvt', string='Đơn vị tính', readonly=True)
    bom_sale_id = fields.Many2one(
        'bom.sale', string='Loại Bom Sale', readonly=True)
    company_id = fields.Many2one(
        'res.company', string='ĐVCS', readonly=True, index=True)
    nganh_hang = fields.Char(string='Ngành hàng', readonly=True, index=True)
    nganh_hang_id = fields.Many2one(
        'mdm.nganh.hang', string='Ngành hàng MDM', readonly=True, index=True)
    active = fields.Boolean(default=True, readonly=True)

    @api.depends('company_id', 'ma_sap')
    def _compute_phan_tram(self):
        if not self:
            return
        if 'ma.hang.phan.tram' not in self.env:
            for rec in self:
                rec.phan_tram = 0.0
            return
        company_ids = list({r.company_id.id for r in self if r.company_id and r.ma_sap})
        ma_saps = list({(r.ma_sap or '').strip() for r in self if r.ma_sap})
        mapping = {}
        if company_ids and ma_saps:
            rows = self.env['ma.hang.phan.tram'].sudo().search([
                ('company_id', 'in', company_ids),
                ('ma_sap', 'in', ma_saps),
            ])
            for row in rows:
                mapping[(row.company_id.id, (row.ma_sap or '').strip())] = row.phan_tram or 0.0
        for rec in self:
            key = (rec.company_id.id, (rec.ma_sap or '').strip())
            rec.phan_tram = mapping.get(key, 0.0)

    @api.model
    def get_sap_meta_map(self, sap_codes):
        """{ma_sap: {ten_hang, nganh_hang_id, ma_mdm}} từ danh mục ma.hang (v_mdm_hang_hoa_bcu)."""
        codes = sorted({(c or '').strip() for c in sap_codes if (c or '').strip()})
        if not codes:
            return {}
        meta_map = {}
        for rec in self.sudo().search([('ma_sap', 'in', codes)]):
            sap = (rec.ma_sap or '').strip()
            if not sap:
                continue
            meta_map[sap] = {
                'ten_hang': rec.ten_hang or '',
                'nganh_hang_id': rec.nganh_hang_id.id if rec.nganh_hang_id else False,
                'ma_mdm': rec.ma_mdm or '',
            }
        return meta_map

    @api.model
    def get_mdm_sap_meta_map(self, sap_codes):
        """{ma_sap: {ten_hang, nganh_hang_id, ma_mdm}} từ mdm.tong.hop.line (đủ mọi mã)."""
        codes = sorted({(c or '').strip() for c in sap_codes if (c or '').strip()})
        if not codes:
            return {}
        meta_map = {}
        for rec in self.env['mdm.tong.hop.line'].sudo().search([('ma_dv', 'in', codes)]):
            sap = (rec.ma_dv or '').strip()
            if not sap or sap in meta_map:
                continue
            th = rec.tong_hop_id
            meta_map[sap] = {
                'ten_hang': rec.ten or (th.ten if th else '') or '',
                'nganh_hang_id': th.nganh_hang.id if th and th.nganh_hang else False,
                'ma_mdm': rec.ma_mdm or '',
            }
        return meta_map

    @api.model
    def get_mdm_sap_codes_set(self, ma_sap_list):
        """Set mã SAP có trong mdm.tong.hop.line (1 query cho cả file import)."""
        codes = sorted({(c or '').strip() for c in ma_sap_list if (c or '').strip()})
        if not codes:
            return set()
        rows = self.env['mdm.tong.hop.line'].sudo().search_read(
            [('ma_dv', 'in', codes)], ['ma_dv'],
        )
        return {(row['ma_dv'] or '').strip() for row in rows if (row.get('ma_dv') or '').strip()}

    @api.model
    def sap_exists_in_mdm(self, ma_sap):
        code = (ma_sap or '').strip()
        if not code:
            return False
        return code in self.get_mdm_sap_codes_set([code])

    @api.model
    def assert_sap_in_catalog(self, ma_sap, label=None):
        """Raise UserError nếu ma_sap không có trong danh mục ma.hang BCU."""
        code = (ma_sap or '').strip()
        if not code:
            return
        if not self.sudo().search_count([('ma_sap', '=', code)]):
            raise UserError(
                _('Mã "%s" không có trong danh mục mã hàng BCU.')
                % (label or code)
            )

    @api.model
    def assert_sap_in_mdm(self, ma_sap, label=None):
        """Raise UserError nếu ma_sap không có trong mdm.tong.hop.line."""
        code = (ma_sap or '').strip()
        if not code:
            return
        if not self.sap_exists_in_mdm(code):
            raise UserError(
                _('Mã "%s" không có trong MDM (mdm.tong.hop.line).')
                % (label or code)
            )

    def action_open_import_wizard(self):
        return {
            'name': _('Import phần trăm'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.ma.hang.phan.tram.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _reload_ma_hang_view(self):
        cr = self.env.cr
        cr.execute("SELECT to_regclass('public.v_mdm_hang_hoa_bcu')")
        if not cr.fetchone()[0]:
            return
        with open(_SQL_VIEW_PATH, 'r', encoding='utf-8-sig') as f:
            cr.execute(f.read())

    def init(self):
        self._reload_ma_hang_view()


_SQL_VIEW_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'sql', 'ma_hang_view.sql',
)
