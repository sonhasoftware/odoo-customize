from odoo import fields, models


class SonhaBomEffect(models.Model):
    _name = 'sonha.bom.effect'
    _description = 'Định mức NVL effect/SAP'
    _rec_name = 'product_name'

    product_code = fields.Char(string='Mã TP effect/SAP', required=True, index=True)
    product_name = fields.Char(string='Tên TP', required=True)
    material_code = fields.Char(string='Mã NVL effect/SAP', required=True, index=True)
    material_name = fields.Char(string='Tên NVL', required=True)
    quantity_per_product = fields.Float(string='SL định mức/1 sản phẩm', digits=(16, 4), default=0.0)
    thickness = fields.Float(string='Độ dày', digits=(16, 4))
    roll_1 = fields.Char(string='Khổ 1')
    roll_2 = fields.Char(string='Khổ 2')
    unit = fields.Char(string='Đơn vị')
