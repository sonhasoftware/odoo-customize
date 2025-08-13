from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class PlantData(models.Model):
    _name = 'plant.data'

    product_code_id = fields.Many2one('declare.md.product', string="Mã vật tư")
    plant = fields.Many2one('stock.warehouse', string="Kho")
    plan_deliver_time = fields.Integer("Thời gian giao hàng dự kiến")
    safety_time = fields.Integer("Số ngày hoàn thành sx")
    safety_stock = fields.Integer("Tồn kho an toàn")
    availability_check = fields.Selection([('02', "02"), ('kp', "KP")], string="Kiểm tra tồn kho", default='kp')
    special_procurement_type = fields.Many2one('special.procument.type', string="Loại cung ứng đặc biệt",
                                               domain="[('plant', 'in', plant)]")
    co_product = fields.Boolean("Sản phầm loại 2")
    procurement_type = fields.Selection([('e', "E"), ('f', "F"), ('x', "X")], string="Loại cung ứng")
    inspection_type_01 = fields.Boolean("Loại kiểm tra chất lượng 01")
    inspection_type_z01 = fields.Boolean("Loại kiểm tra chất lượng Z01")
    inspection_type_04 = fields.Boolean("Loại kiểm tra chất lượng 04")
    inspection_type_z04 = fields.Boolean("Loại kiểm tra chất lượng Z04")
    inspection_type_05 = fields.Boolean("Loại kiểm tra chất lượng 05")
    inspection_type_z05 = fields.Boolean("Loại kiểm tra chất lượng Z05")
    inspection_type_08 = fields.Boolean("Loại kiểm tra chất lượng 08")
    inspection_type_z08 = fields.Boolean("Loại kiểm tra chất lượng Z08")
    inspection_type_10 = fields.Boolean("Loại kiểm tra chất lượng 10")
    inspection_type_z10 = fields.Boolean("Loại kiểm tra chất lượng Z10")
    inspection_type_89 = fields.Boolean("Loại kiểm tra chất lượng 89")
    inspection_type_z89 = fields.Boolean("Loại kiểm tra chất lượng Z89")
    purchasing_group = fields.Many2one('purchasing.group', string="Nhóm mua hàng")
    profit_center = fields.Many2one('profit.center', string="Trung tâm ghi nhận doanh thu",
                                    domain="[('plant', '=', plant)]")
    mrp_controller = fields.Many2one('mrp.controller', string="Nhóm lập kế hoạch vật tư",
                                     domain="[('plant', 'in', plant)]")
    valuation_class = fields.Many2one('valuation.class', string="Nhóm tài khoản tồn kho",
                                   domain="[('id', 'in', domain_valuation_class)]")
    overhead_group = fields.Many2one('overhead.group', string="Nhóm chi phí chung", domain="[('plant', '=', plant)]")
    material_type = fields.Many2one('x.material.type', compute="compute_material_type", store=True)
    check_stock = fields.Boolean(compute="compute_material_type", store=True)
    check_shi = fields.Boolean(compute="compute_material_type", store=True)
    domain_valuation_class = fields.Many2many('valuation.class', compute="compute_domain_field", store=True)
    md_product_id = fields.Many2one('md.product')

    @api.depends('product_code_id.product_type', 'plant')
    def compute_material_type(self):
        group_1 = ['2201', '2202']
        group_2 = ['2101', '2102', '2103']
        for r in self:
            purchasing_code = None
            r.procurement_type = None
            mrp_code = None
            profit_code = None
            if r.product_code_id.product_type and r.plant:
                if r.product_code_id.product_type.x_code not in ['Z100', 'Z101'] and r.plant.plant in group_1:
                    profit_code = "220199" if r.plant.plant == "2201" else "220299"
                if r.product_code_id.product_type.x_code not in ['Z100', 'Z300', 'Z500', 'Z101'] and r.plant.plant in group_1:
                    purchasing_code = "500"
                    mrp_code = "000"
                    r.procurement_type = 'f'
                if r.product_code_id.product_type.x_code == "Z500" and r.plant.plant in group_1:
                    purchasing_code = "200"
                if r.product_code_id.product_type.x_code == "Z101" and r.plant.plant in group_1:
                    purchasing_code = "100"
                if r.product_code_id.product_type.x_code not in ['Z100', 'Z101'] and r.plant.plant in group_2:
                    mrp_code = "000"
                    r.procurement_type = 'f'
                if r.plant.plant == "1001":
                    mrp_code = "000"
                    r.procurement_type = 'f'
                if r.plant.plant not in (group_1 + group_2):
                    r.check_shi = True
                    r.overhead_group = None
                else:
                    r.check_shi = False
            purchasing_group = self.env['purchasing.group'].sudo().search([('purchasing_group_code', '=', purchasing_code)])
            mrp = self.env['mrp.controller'].sudo().search([('mrp_controller', '=', mrp_code)])
            profit_center = self.env['profit.center'].sudo().search([('name', '=', profit_code)])
            r.purchasing_group = purchasing_group.id
            r.mrp_controller = mrp.id
            r.profit_center = profit_center.id
            r.material_type = r.product_code_id.product_type.id if r.product_code_id.product_type else None
            r.plan_deliver_time = 15 if r.product_code_id.product_type.x_code not in ['Z100', 'Z101', 'Z102', 'Z300'] else 0
            if r.product_code_id.product_type.x_code in ['Z500', 'Z600', 'Z800']:
                r.check_stock = True
                r.special_procurement_type = None
                r.plan_deliver_time = 0
                r.safety_time = 0
                r.safety_stock = 0
                r.mrp_controller = None
                r.co_product = False
                r.procurement_type = None
                r.valuation_class = None
                r.overhead_group = None
                r.inspection_type_01 = False
                r.inspection_type_z01 = False
                r.inspection_type_04 = False
                r.inspection_type_z04 = False
                r.inspection_type_05 = False
                r.inspection_type_z05 = False
                r.inspection_type_08 = False
                r.inspection_type_z08 = False
                r.inspection_type_10 = False
                r.inspection_type_z10 = False
                r.inspection_type_89 = False
                r.inspection_type_z89 = False
            else:
                r.check_stock = False

    @api.onchange('mrp_controller')
    def onchange_procurement_type(self):
        for r in self:
            if r.mrp_controller and r.mrp_controller.mrp_controller == "000":
                r.procurement_type = 'f'
            elif r.mrp_controller and r.mrp_controller.mrp_controller in ['102', '103']:
                r.procurement_type = 'e'
            elif r.mrp_controller and r.mrp_controller.mrp_controller in ['101', '104']:
                r.procurement_type = 'x'
            else:
                r.procurement_type = None

    @api.depends('material_type', 'plant')
    def compute_domain_field(self):
        group_1 = ['2201', '2202']
        group_2 = ['2101', '2102', '2103']
        for r in self:
            if r.plant and r.plant.plant in group_1:
                if r.material_type and r.material_type.x_code in ['Z100', 'Z101', 'Z200', 'Z300', 'Z205']:
                    domain_valuation_class = self.env['valuation.class'].sudo().search([('company_ids', 'in', r.plant.company_id.id)])
                    r.domain_valuation_class = domain_valuation_class
                elif r.material_type and r.material_type.x_code not in ['Z100', 'Z101', 'Z200', 'Z300', 'Z205']:
                    domain_valuation_class = self.env['valuation.class'].sudo().search([('company_ids', 'in', r.plant.company_id.id),
                                                                                        ('material_type', 'in', r.material_type.id)])
                    r.domain_valuation_class = domain_valuation_class
                else:
                    r.domain_valuation_class = None
            elif r.plant and r.plant.plant in group_2:
                if r.material_type and r.material_type.x_code in ['Z100', 'Z101', 'Z102']:
                    domain_valuation_class = self.env['valuation.class'].sudo().search([('company_ids', 'in', r.plant.company_id.id)])
                    r.domain_valuation_class = domain_valuation_class
                elif r.material_type and r.material_type.x_code not in ['Z100', 'Z101', 'Z102']:
                    domain_valuation_class = self.env['valuation.class'].sudo().search([('company_ids', 'in', r.plant.company_id.id),
                                                                                        ('material_type', 'in', r.material_type.id)])
                    r.domain_valuation_class = domain_valuation_class
                else:
                    r.domain_valuation_class = None
            elif r.plant and r.plant.plant not in (group_1 + group_2):
                domain_valuation_class = self.env['valuation.class'].sudo().search([('company_ids', 'in', r.plant.company_id.id),
                                                                                    ('material_type', 'in', r.material_type.id)])
                r.domain_valuation_class = domain_valuation_class
            else:
                r.domain_valuation_class = None

