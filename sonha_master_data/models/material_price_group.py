from odoo import models, fields


class MaterialPriceGroup(models.Model):
    _name = 'material.price.group'
    _rec_name = 'x_present_note'

    code = fields.Char("Mã nhóm giá mặt hàng", required=True)
    x_present_note = fields.Char("Diễn giải hiện tại", required=True)
    x_sap_note = fields.Char("Diễn giải trên SAP")
