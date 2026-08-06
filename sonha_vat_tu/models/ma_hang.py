# -*- coding: utf-8 -*-
import os as _os

from odoo import api, fields, models, _


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

    @api.model
    def _display_ma_code_only(self):
        return bool(self.env.context.get('vat_tu_display_ma_code_only'))

    @api.model
    def _label_ma_code_only(self, rec):
        return (rec.ma_sap or '').strip() or str(rec.id)

    @api.depends('ma_sap', 'ten_hang')
    def _compute_display_name(self):
        if not self._display_ma_code_only():
            return super()._compute_display_name()
        for rec in self:
            rec.display_name = self._label_ma_code_only(rec)

    def name_get(self):
        if not self._display_ma_code_only():
            return super().name_get()
        return [(rec.id, self._label_ma_code_only(rec)) for rec in self]

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, order=None):
        args = list(args or [])
        if name:
            args += ['|', ('ma_sap', operator, name), ('ten_hang', operator, name)]
        return self._search(args, limit=limit, order=order)

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
    def get_ma_linh_vuc_map(self, ma_codes):
        """{ma_dv: ma_linh_vuc} từ view QL v_mdm_hang_hoa_bcu."""
        codes = sorted({(c or '').strip() for c in ma_codes if (c or '').strip()})
        if not codes:
            return {}
        cr = self.env.cr
        cr.execute("SELECT to_regclass('public.v_mdm_hang_hoa_bcu')")
        if not cr.fetchone()[0]:
            return {}
        cr.execute(
            """
            SELECT TRIM(ma_dv) AS ma_dv, TRIM(ma_linh_vuc) AS ma_linh_vuc
            FROM v_mdm_hang_hoa_bcu
            WHERE TRIM(ma_dv) = ANY(%s)
            """,
            (codes,),
        )
        result = {}
        for ma_dv, ma_linh_vuc in cr.fetchall():
            code = (ma_dv or '').strip()
            if not code or code in result:
                continue
            result[code] = (ma_linh_vuc or '').strip()
        return result

    @api.model
    def sap_exists_in_mdm(self, ma_sap):
        code = (ma_sap or '').strip()
        if not code:
            return False
        return code in self.get_mdm_sap_codes_set([code])

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
