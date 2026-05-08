from odoo import fields, models


class SonhaBomEffect(models.Model):
    _name = 'sonha.bom.bcu'
    _description = 'Định mức NVL effect/SAP'
    _rec_name = 'product_name'

    ma_tp = fields.Char(string='Mã TP effect/SAP', required=True, index=True)
    ten_tp = fields.Char(string='Tên TP', required=True)
    ma_nvl = fields.Char(string='Mã NVL effect/SAP', required=True, index=True)
    ten_nvl = fields.Char(string='Tên NVL', required=True)
    dinh_muc = fields.Float(string='SL định mức/1 sản phẩm', digits=(16, 4), default=0.0)
    do_day = fields.Float(string='Độ dày', digits=(16, 4))
    kho_1 = fields.Char(string='Khổ 1')
    kho_2 = fields.Char(string='Khổ 2')
    dvcs = fields.Many2one('res.company', string='Đơn vị')
