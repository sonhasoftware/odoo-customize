# -*- coding: utf-8 -*-
from odoo import _, fields, models


class Bom(models.Model):
    _name = 'bom'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BOM'
    _rec_name = 'ma_tp'
    _order = 'company_id, ma_tp, ma_nvl'

    ma_bom = fields.Char(string='Mã BOM', index=True)
    ma_tp = fields.Char(string='Mã thành phẩm', index=True)
    ten_tp = fields.Char(string='Tên thành phẩm')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    company_id = fields.Many2one(
        'res.company', string='Đơn vị', index=True,
        default=lambda self: self.env.company)
    sl_dinh_muc = fields.Float(
        string='Số lượng định mức / 1 sản phẩm', digits=(16, 3), default=0.0)
    do_day = fields.Float(string='Độ dày', digits=(16, 2))
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0))
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0))

    _sql_constraints = [
        ('uniq_company_bom_nvl', 'unique(company_id, ma_bom, ma_nvl)',
         'BOM đã tồn tại theo đơn vị, mã BOM và mã NVL!'),
    ]

    def action_download_bom_template(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/sonha_vat_tu/static/xls/bom_template.xlsx',
            'target': 'self',
        }

    def action_open_import_bom_wizard(self):
        return {
            'name': _('Import BOM'),
            'type': 'ir.actions.act_window',
            'res_model': 'import.bom.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_company_id': self.env.company.id,
            },
        }
