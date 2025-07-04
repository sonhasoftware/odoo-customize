from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AlternativeUom(models.Model):
    _name = 'alternative.uom'

    product_code_id = fields.Many2one('md.product', string="Mã vật tư")
    alternative_unit = fields.Many2one('uom.uom', string="Đơn vị thay thế")
    denominator = fields.Float("Mẫu số")
    numerator = fields.Float("Tử số")
    unit_measure = fields.Boolean("Đơn vị tính thứ 2", compute="compute_get_default", store=True)
    char_name = fields.Many2one('uom.characteristic', string="Tên thuộc tính")

    @api.depends('product_code_id.basic_data.malt_prdhier')
    def compute_get_default(self):
        alt_uom = self.env['uom.uom'].sudo().search([('name', '=', "Cây")])
        characteristic = self.env['uom.characteristic'].sudo().search([('characteristic', '=', "Z_CAY_KG")])
        list_alt_uom = ['00210001000001', '00220001000001', '00230001000001']
        for r in self:
            if r.product_code_id.basic_data.malt_prdhier and r.product_code_id.basic_data.malt_prdhier.code in list_alt_uom:
                r.alternative_unit = alt_uom.id
                r.char_name = characteristic.id
                r.unit_measure = True
            else:
                r.unit_measure = False
                r.char_name = None




