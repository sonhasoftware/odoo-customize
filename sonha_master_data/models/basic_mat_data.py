from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BasicMatData(models.Model):
    _name = 'basic.mat.data'

    old_product_code = fields.Char("Mã vật tư cũ", size=18)
    main_unit = fields.Many2one('uom.uom', string="Đơn vị tính chính")
    product_group = fields.Many2one('x.mch.list', string="Nhóm mặt hàng", domain="[('level', '=', 5)]")
    x_mch_level_1 = fields.Many2one('x.mch.list', string="Nhóm mch cấp 1", compute="filter_mch_all_level", store=True)
    x_mch_level_2 = fields.Many2one('x.mch.list', string="Nhóm mch cấp 2", compute="filter_mch_all_level", store=True)
    x_mch_level_3 = fields.Many2one('x.mch.list', string="Nhóm mch cấp 3", compute="filter_mch_all_level", store=True)
    x_mch_level_4 = fields.Many2one('x.mch.list', string="Nhóm mch cấp 4", compute="filter_mch_all_level", store=True)
    material = fields.Char("Chất liệu")
    surface = fields.Char("Bề mặt")
    batch_management = fields.Boolean("Quản lý theo lô")
    sale_division = fields.Many2one('x.division', string="Mã lĩnh vực")
    malt_prdhier = fields.Many2one('x.product.hierarchy', "Cây cấu trúc hàng hóa cấp 3", domain="[('level', '=', 3)]")
    gross_weight = fields.Char("Trọng lượng grooss")
    net_weight = fields.Char("Trọng lượng net")
    weight_unit = fields.Many2one('uom.uom', string="Đơn vị trọng lượng",
                                  domain="[('category_id.name', '=', 'Khối lượng')]")
    volume = fields.Char("Thể tích")
    volume_unit = fields.Many2one('uom.uom', "Đơn vị thể tích",
                                  domain="[('category_id.name', '=', 'Thể tích')]")
    size = fields.Char("Kích thước")
    product_code_id = fields.Many2one('md.product', string="Mã vật tư")
    required_weight_unit = fields.Boolean()
    required_volume_unit = fields.Boolean()

    @api.onchange('gross_weight', 'net_weight', 'volume')
    def _compute_is_required_x(self):
        for rec in self:
            if rec.gross_weight or rec.net_weight:
                rec.required_weight_unit = True
            else:
                rec.required_weight_unit = False
            if rec.volume:
                rec.required_volume_unit = True
            else:
                rec.required_volume_unit = False

    @api.onchange('product_group', 'x_mch_level_2')
    def _onchange_volume_unit(self):
        mch_list_m3 = ['440', '441', '442']
        mch_list_l = ['449', '448', '444', '443']
        except_mch_list = ['440029001', '440019001', '448010102', '448010103', '448010104']
        for r in self:
            unit = None
            if r.x_mch_level_2 and r.x_mch_level_2.x_mch_code in mch_list_m3:
                unit = "m³"
            if r.x_mch_level_2 and r.x_mch_level_2.x_mch_code in mch_list_l:
                unit = "L"
            volume_unit = self.env['uom.uom'].sudo().search([('name', '=', unit)], limit=1)
            if volume_unit and r.product_group.x_mch_code not in except_mch_list:
                r.volume_unit = volume_unit.id
                r.required_volume_unit = True
            else:
                r.volume_unit = None
                r.required_volume_unit = False

    @api.depends('product_group')
    def filter_mch_all_level(self):
        for r in self:
            if r.product_group:
                r.x_mch_level_4 = r.product_group.x_parent_id.id
                r.x_mch_level_3 = r.product_group.x_parent_id.x_parent_id.id
                r.x_mch_level_2 = r.product_group.x_parent_id.x_parent_id.x_parent_id.id
                r.x_mch_level_1 = r.product_group.x_parent_id.x_parent_id.x_parent_id.x_parent_id.id
            else:
                r.x_mch_level_4 = None
                r.x_mch_level_3 = None
                r.x_mch_level_2 = None
                r.x_mch_level_1 = None

    def create(self, vals):
        alt_uom = self.env['uom.uom'].sudo().search([('name', '=', "Cây")])
        characteristic = self.env['uom.characteristic'].sudo().search([('characteristic', '=', "Z_CAY_KG")])
        list_alt_uom = ['00210001000001', '00220001000001', '00230001000001']
        res = super(BasicMatData, self).create(vals)
        if res.malt_prdhier.code in list_alt_uom:
            vals = {
                'alternative_unit': alt_uom.id if alt_uom else None,
                'unit_measure': True,
                'char_name': characteristic.id if characteristic else None,
                'product_code_id': res.product_code_id.id,
            }
            self.env['alternative.uom'].sudo().create(vals)
            res.product_code_id.sudo().write({'have_alt_uom': True})
        return res

    def write(self, vals):
        alt_uom = self.env['uom.uom'].sudo().search([('name', '=', "Cây")])
        characteristic = self.env['uom.characteristic'].sudo().search([('characteristic', '=', "Z_CAY_KG")])
        list_alt_uom = ['00210001000001', '00220001000001', '00230001000001']
        res = super(BasicMatData, self).write(vals)
        if 'malt_prdhier' in vals:
            for r in self:
                if r.malt_prdhier and r.malt_prdhier.code in list_alt_uom:
                    self.env['alternative.uom'].search([('product_code_id', '=', r.product_code_id.id)]).sudo().unlink()
                    vals = {
                        'alternative_unit': alt_uom.id if alt_uom else None,
                        'unit_measure': True,
                        'char_name': characteristic.id if characteristic else None,
                        'product_code_id': r.product_code_id.id,
                    }
                    self.env['alternative.uom'].sudo().create(vals)
                    r.product_code_id.sudo().write({'have_alt_uom': True})
        return res




