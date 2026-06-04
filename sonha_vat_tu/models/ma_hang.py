# -*- coding: utf-8 -*-
import os as _os

from odoo import _, fields, models


class MaHang(models.Model):
    _name = 'ma.hang'
    _description = 'Danh mục mã hàng'
    _rec_name = 'ma_sap'
    _order = 'ma_sap'

    mdm_line_id = fields.Many2one(
        'mdm.tong.hop.line', string='Dòng MDM', index=True, ondelete='restrict')
    mdm_id = fields.Many2one(
        'mdm.tong.hop', string='Hàng hóa MDM', related='mdm_line_id.tong_hop_id',
        store=True, readonly=True, index=True)
    ma_mdm = fields.Char(
        string='Mã MDM', related='mdm_line_id.ma_mdm', store=True, readonly=True, index=True)
    ma_sap = fields.Char(string='Mã đơn vị', index=True, required=True)
    ten_hang = fields.Char(
        string='Tên hàng hóa', related='mdm_line_id.ten', store=True, readonly=True)
    don_vi_tinh_id = fields.Many2one(
        'mdm.dvt', string='Đơn vị tính', related='mdm_line_id.dvt',
        store=True, readonly=True)
    bom_sale_id = fields.Many2one(
        'bom.sale', string='Loại Bom Sale', related='mdm_line_id.bom_sale',
        store=True, readonly=True)
    company_id = fields.Many2one(
        'res.company', string='ĐVCS', related='mdm_line_id.dvcs',
        store=True, readonly=True, index=True)
    nganh_hang = fields.Text(
        string='Ngành hàng', related='mdm_id.nganh_hang.ten',
        store=True, readonly=True, index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('vtc_ma_hang_sap_uniq', 'unique(ma_sap)', 'Mã đơn vị phải duy nhất!'),
        ('vtc_ma_hang_mdm_line_uniq', 'unique(mdm_line_id)', 'Dòng MDM đã được đồng bộ!'),
    ]

    def action_sync_from_mdm(self):
        MdmLine = self.env['mdm.tong.hop.line'].sudo()
        synced = 0
        for line in MdmLine.search([('ma_dv', '!=', False)]):
            ma_sap = (line.ma_dv or '').strip()
            if not ma_sap:
                continue
            vals = {
                'mdm_line_id': line.id,
                'ma_sap': ma_sap,
                'active': True,
            }
            rec = self.sudo().search([('ma_sap', '=', ma_sap)], limit=1)
            if rec:
                rec.write(vals)
            else:
                self.sudo().create(vals)
            synced += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ mã hàng'),
                'message': _('Đã đồng bộ %s mã hàng từ MDM.') % synced,
                'type': 'success',
                'sticky': False,
            },
        }

    def init(self):
        with open(_SQL_SYNC_PATH, 'r', encoding='utf-8-sig') as f:
            self.env.cr.execute(f.read())


_SQL_SYNC_PATH = _os.path.join(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
    'data', 'sql', 'ma_hang_mdm_sync.sql',
)
