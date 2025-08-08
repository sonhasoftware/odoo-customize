from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class WizardMDMaterial(models.TransientModel):
    _name = 'wizard.md.material'

    product_type = fields.Many2one('x.material.type', string="Loại vật tư", required=True)
    line = fields.Boolean("Dòng sản phẩm", default=True, compute="compute_hide_show", store=True)
    stage = fields.Boolean("Công đoạn/Sản phẩm", default=True, compute="compute_hide_show", store=True)
    brand = fields.Boolean("Nhãn hiệu/Chủng loại", default=False, compute="compute_hide_show", store=True)
    model = fields.Boolean("Model", default=False, compute="compute_hide_show", store=True)
    style = fields.Boolean("Kiểu dáng", default=False, compute="compute_hide_show", store=True)
    capacity = fields.Boolean("Dung tích", default=False, compute="compute_hide_show", store=True)
    power = fields.Boolean("Công suất", default=False, compute="compute_hide_show", store=True)
    substance = fields.Boolean("Chất liệu", default=False, compute="compute_hide_show", store=True)
    surface = fields.Boolean("Kiểu bề mặt/Độ bóng", default=False, compute="compute_hide_show", store=True)
    diameter = fields.Boolean("Đường kính", default=False, compute="compute_hide_show", store=True)
    thickness = fields.Boolean("Độ dày", default=False, compute="compute_hide_show", store=True)
    size = fields.Boolean("Chiều dài, rộng, cao", default=False, compute="compute_hide_show", store=True)
    chemical = fields.Boolean("TP hóa học", default=False, compute="compute_hide_show", store=True)
    color = fields.Boolean("Màu sắc", default=False, compute="compute_hide_show", store=True)
    other = fields.Boolean("Khác", default=False, compute="compute_hide_show", store=True)
    tech_spec = fields.Boolean("Thông số kỹ thuật", default=False, compute="compute_hide_show", store=True)
    specific = fields.Boolean("Đặc thù/Mục đích", default=False, compute="compute_hide_show", store=True)
    country = fields.Boolean("Nước sản xuất", default=False, compute="compute_hide_show", store=True)
    name_pr = fields.Boolean("Tên", default=False, compute="compute_hide_show", store=True)

    product_line = fields.Many2one('product.line', string="Dòng sản phẩm",
                                   domain="[('material_type', 'in', product_type)]")
    product_stage = fields.Many2one('product.stage', string="Công đoạn/Sản phẩm",
                                    domain="[('product_line', '=', product_line)]")
    product_brand = fields.Many2one('product.brand', string="Nhãn hiệu/Chủng loại")
    product_model = fields.Many2one('product.model', string="Model")
    product_style = fields.Many2one('product.style', string="Kiểu dáng")
    product_capacity = fields.Many2one('product.capacity', string="Dung tích")
    product_power = fields.Many2one('product.capacity', string="Công suất")
    product_substance = fields.Many2one('product.substance', string="Chất liệu")
    product_surface = fields.Many2one('product.surface', string="Kiểu bề mặt")
    product_diameter = fields.Many2one('product.diameter', string="Đường kính")
    product_thickness = fields.Many2one('product.thickness', string="Độ dày")
    product_size = fields.Many2one('product.size', string="Chiều dài, rộng, cao")
    product_chemical = fields.Many2one('product.chemical', string="TP hóa học")
    product_color = fields.Many2one('product.color', string="Màu sắc")
    product_other = fields.Many2one('product.other', string="Khác")
    product_other_char = fields.Char("Khác")
    product_tech_spec = fields.Char("Thông số kỹ thuật")
    product_specific = fields.Char("Đặc thù/Mục đích")
    product_country = fields.Many2one('res.country', string="Nước sản xuất")
    product_name = fields.Char("Tên vật tư")

    declare_product = fields.Many2many('declare.md.product', string="Vật tư trùng")

    @api.depends('product_line', 'product_stage', 'product_type.x_code')
    def compute_hide_show(self):
        for r in self:
            if r.product_type.x_code in ['Z500', 'Z205']:
                r.name_pr = True
                r.line = False
                r.stage = False
                r.brand = False
                r.model = False
                r.style = False
                r.capacity = False
                r.power = False
                r.substance = False
                r.surface = False
                r.diameter = False
                r.thickness = False
                r.size = False
                r.chemical = False
                r.color = False
                r.other = False
                r.tech_spec = False
                r.specific = False
                r.country = False
            elif r.product_type.x_code not in ['Z500', 'Z205']:
                r.line = True
                r.stage = True
                if r.product_type.x_code in ['Z100', 'Z101'] and r.product_line and r.product_stage or (
                        r.product_type.x_code == "Z200" and r.product_line.is_main_material):
                    name_rule = self.env['product.name.rule'].sudo().search([('product_line', '=', r.product_line.id),
                                                                             ('product_stage', '=', r.product_stage.id)])
                    if name_rule:
                        r.brand = name_rule.brand
                        r.model = name_rule.model
                        r.style = name_rule.style
                        r.capacity = name_rule.capacity
                        r.power = name_rule.power
                        r.substance = name_rule.substance
                        r.surface = name_rule.surface
                        r.diameter = name_rule.diameter
                        r.thickness = name_rule.thickness
                        r.size = name_rule.size
                        r.chemical = name_rule.chemical
                        r.color = name_rule.color
                        r.other = name_rule.other
                        r.country = False
                        r.specific = False
                        r.tech_spec = False
                    else:
                        r.brand = False
                        r.model = False
                        r.style = False
                        r.capacity = False
                        r.power = False
                        r.substance = False
                        r.surface = False
                        r.diameter = False
                        r.thickness = False
                        r.size = False
                        r.chemical = False
                        r.color = False
                        r.other = False
                        r.country = False
                        r.specific = False
                        r.tech_spec = False
                elif r.product_type.x_code and r.product_type.x_code not in ['Z100', 'Z101', 'Z205', 'Z200'] or (
                        r.product_line and r.product_type.x_code == "Z200" and not r.product_line.is_main_material):
                    r.stage = False
                    r.brand = True
                    r.model = True
                    r.tech_spec = True
                    r.color = True
                    r.country = True
                    r.specific = True
                    r.style = False
                    r.capacity = False
                    r.power = False
                    r.substance = False
                    r.surface = False
                    r.diameter = False
                    r.thickness = False
                    r.size = False
                    r.chemical = False
                    r.other = False
            elif not r.product_type.x_code or not r.product_line:
                r.brand = False
                r.model = False
                r.style = False
                r.capacity = False
                r.power = False
                r.substance = False
                r.surface = False
                r.diameter = False
                r.thickness = False
                r.size = False
                r.chemical = False
                r.color = False
                r.other = False
                r.country = False
                r.specific = False
                r.tech_spec = False

    @api.onchange('product_line', 'product_stage')
    def onchange_name_product(self):
        self.product_brand = None
        self.product_model = None
        self.product_style = None
        self.product_capacity = None
        self.product_power = None
        self.product_substance = None
        self.product_surface = None
        self.product_diameter = None
        self.product_thickness = None
        self.product_size = None
        self.product_chemical = None
        self.product_color = None
        self.product_other_char = None

    @api.onchange('product_type')
    def onchange_name_product(self):
        self.product_line = None
        self.product_stage = None
        self.product_brand = None
        self.product_model = None
        self.product_style = None
        self.product_capacity = None
        self.product_power = None
        self.product_substance = None
        self.product_surface = None
        self.product_diameter = None
        self.product_thickness = None
        self.product_size = None
        self.product_chemical = None
        self.product_color = None
        self.product_other_char = None
        self.product_country = None
        self.product_tech_spec = None
        self.product_specific = None

    def action_confirm(self):
        if self.product_type and self.product_line and self.product_type.x_code not in ['Z500', 'Z205']:
            exist_product = self.env['declare.md.product'].sudo().search([('product_type', '=', self.product_type.id),
                                                                          ('product_line', '=', self.product_line.id)])
            if self.product_stage:
                exist_product = exist_product.filtered(lambda x: x.product_stage == self.product_stage)
            if self.product_brand:
                exist_product = exist_product.filtered(lambda x: x.product_brand == self.product_brand)
            if self.product_model:
                exist_product = exist_product.filtered(lambda x: x.product_model == self.product_model)
            if self.product_style:
                exist_product = exist_product.filtered(lambda x: x.product_style == self.product_style)
            if self.product_capacity:
                exist_product = exist_product.filtered(lambda x: x.product_capacity == self.product_capacity)
            if self.product_power:
                exist_product = exist_product.filtered(lambda x: x.product_power == self.product_power)
            if self.product_substance:
                exist_product = exist_product.filtered(lambda x: x.product_substance == self.product_substance)
            if self.product_surface:
                exist_product = exist_product.filtered(lambda x: x.product_surface == self.product_surface)
            if self.product_diameter:
                exist_product = exist_product.filtered(lambda x: x.product_diameter == self.product_diameter)
            if self.product_thickness:
                exist_product = exist_product.filtered(lambda x: x.product_thickness == self.product_thickness)
            if self.product_size:
                exist_product = exist_product.filtered(lambda x: x.product_size == self.product_size)
            if self.product_chemical:
                exist_product = exist_product.filtered(lambda x: x.product_chemical == self.product_chemical)
            if self.product_color:
                exist_product = exist_product.filtered(lambda x: x.product_color == self.product_color)
            if self.product_other_char:
                exist_product = exist_product.filtered(lambda x: x.product_other == self.product_other)
            if self.product_country:
                exist_product = exist_product.filtered(lambda x: x.product_country == self.product_country)
            if self.product_tech_spec:
                exist_product = exist_product.filtered(lambda x: x.product_tech_spec == self.product_tech_spec)
            if self.product_specific:
                exist_product = exist_product.filtered(lambda x: x.product_specific == self.product_specific)
            if exist_product:
                self.declare_product = [(6, 0, exist_product.ids)]
            else:
                self.declare_product = [(6, 0, [])]
        elif self.product_type and self.product_type.x_code in ['Z500', 'Z205']:
            exist_product = self.env['declare.md.product'].sudo().search([('product_type', '=', self.product_type.id)])
            if self.product_name:
                exist_product = exist_product.filtered(lambda x: x.product_name == self.product_name)
            if exist_product:
                self.declare_product = [(6, 0, exist_product.ids)]
            else:
                self.declare_product = [(6, 0, [])]
