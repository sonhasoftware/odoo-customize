# -*- coding: utf-8 -*-
from odoo import fields, models


class TraCuuBomLine(models.TransientModel):
    """Kết quả tra cứu BOM — đổ từ SQL raw trong wizard, không qua fn B3."""

    _name = 'tra.cuu.bom.line'
    _description = 'Dòng tra cứu BOM'
    _order = 'ma_tp_goc, cap_bom, ma_tp_cha, ma_con, don_vi_kd_code, id'

    wizard_id = fields.Many2one(
        'tra.cuu.bom.wizard', string='Wizard', ondelete='cascade', index=True)

    don_vi_kd_code = fields.Char(string='Mã đơn vị KD')
    ma_tp_goc = fields.Char(string='Mã TP gốc', index=True)
    ten_tp_goc = fields.Char(string='Tên TP gốc')
    ma_tp_cha = fields.Char(string='Mã TP cha', index=True)
    ten_tp_cha = fields.Char(string='Tên TP cha')
    ma_con = fields.Char(string='Mã con', index=True)
    ten_con = fields.Char(string='Tên con')
    cap_bom = fields.Integer(string='Cấp BOM')
    chi_nhanh = fields.Char(string='Chi nhánh BOM')
    sl_thuc_te = fields.Float(string='Định mức', digits=(16, 6))
    ma_hang = fields.Char(string='Mã hàng / EFFECT')

    qty_kh_t0 = fields.Float(string='Kế hoạch T0', digits=(16, 2))
    qty_kh_t1 = fields.Float(string='Kế hoạch T1', digits=(16, 2))
    qty_kh_t2 = fields.Float(string='Kế hoạch T2', digits=(16, 2))
    qty_kh_t3 = fields.Float(string='Kế hoạch T3', digits=(16, 2))
    qty_nvl_t0 = fields.Float(string='Vật tư cần T0', digits=(16, 3))
    qty_nvl_t1 = fields.Float(string='Vật tư cần T1', digits=(16, 3))
    qty_nvl_t2 = fields.Float(string='Vật tư cần T2', digits=(16, 3))
    qty_nvl_t3 = fields.Float(string='Vật tư cần T3', digits=(16, 3))
