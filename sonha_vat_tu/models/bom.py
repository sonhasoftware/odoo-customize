# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)



class Bom(models.Model):
    _name = 'bom'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BOM'
    _rec_name = 'ma_tp'
    _order = 'ma_tp, ma_nvl'

    ma_tp = fields.Char(string='Mã thành phẩm', index=True)
    ten_tp = fields.Char(string='Tên thành phẩm')
    ma_nvl = fields.Char(string='Mã NVL', index=True)
    ten_nvl = fields.Char(string='Tên NVL')
    sl_dinh_muc = fields.Float(
        string='Số lượng định mức', digits=(16, 3), default=0.0)
    sl_spdm = fields.Float(string='Số lượng SPĐM', digits=(16, 3), default=1.0)
    do_day = fields.Float(string='Độ dày', digits=(16, 2))
    kho_1 = fields.Float(string='Khổ 1', digits=(16, 0))
    kho_2 = fields.Float(string='Khổ 2', digits=(16, 0))

    _sql_constraints = [
        ('uniq_bom_tp_nvl', 'unique(ma_tp, ma_nvl)',
         'BOM đã tồn tại theo mã thành phẩm và mã NVL!'),
    ]

    # def action_download_bom_template(self):
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': '/sonha_vat_tu/static/xls/bom_templates.xlsx',
    #         'target': 'self',
    #     }
    #
    # def action_open_import_bom_wizard(self):
    #     return {
    #         'name': _('Import BOM'),
    #         'type': 'ir.actions.act_window',
    #         'res_model': 'import.bom.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #     }
    #

