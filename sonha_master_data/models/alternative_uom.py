from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class AlternativeUom(models.Model):
    _name = 'alternative.uom'

    product_code_id = fields.Many2one('declare.md.product', string="Mã vật tư")
    alternative_uom = fields.Many2one('sonha.uom', string="Đơn vị thay thế", required=True)
    denominator = fields.Float("Mẫu số")
    numerator = fields.Float("Tử số")
    unit_measure = fields.Boolean("Đơn vị tính thứ 2", compute="compute_get_default", store=True)
    char_name = fields.Many2one('uom.characteristic', string="Tên thuộc tính")
    md_product_id = fields.Many2one('md.product')

    @api.depends('product_code_id.basic_data.malt_prdhier')
    def compute_get_default(self):
        list_alt_uom = ['00210001000001', '00220001000001', '00230001000001']
        for r in self:
            if r.product_code_id.basic_data.malt_prdhier and r.product_code_id.basic_data.malt_prdhier.code in list_alt_uom:
                alt_uom = self.env['sonha.uom'].sudo().search([('name', '=', "Cây")])
                characteristic = self.env['uom.characteristic'].sudo().search([('characteristic', '=', "Z_CAY_KG")])
                r.alternative_uom = alt_uom.id
                r.char_name = characteristic.id
                r.unit_measure = True
            else:
                r.unit_measure = False
                r.char_name = None




