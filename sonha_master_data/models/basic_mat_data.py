from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BasicMatData(models.Model):
    _name = 'basic.mat.data'

    old_product_code = fields.Char("Mã vật tư cũ", size=18)
    main_uom = fields.Many2one('sonha.uom', string="Đơn vị tính chính")
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
    weight_uom = fields.Many2one('sonha.uom', string="Đơn vị trọng lượng",
                                 domain="[('category', '=', 'mass')]")
    volume = fields.Char("Thể tích")
    volume_uom = fields.Many2one('sonha.uom', "Đơn vị thể tích",
                                 domain="[('category', '=', 'volume')]")
    size = fields.Char("Kích thước")
    product_code_id = fields.Many2one('declare.md.product', string="Mã vật tư")
    required_weight_unit = fields.Boolean()
    required_volume_unit = fields.Boolean()
    md_product_id = fields.Many2one('md.product')

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
            volume_unit = self.env['sonha.uom'].sudo().search([('name', '=', unit)], limit=1)
            if volume_unit and r.product_group.x_mch_code not in except_mch_list:
                r.volume_uom = volume_unit.id
                r.required_volume_unit = True
            else:
                r.volume_uom = None
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





