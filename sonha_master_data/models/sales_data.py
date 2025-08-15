from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SalesData(models.Model):
    _name = 'sales.data'

    product_code_id = fields.Many2one('declare.md.product', string="Mã vật tư")
    sale_organization = fields.Many2one('sale.organization', string="Tổ chức bán hàng",
                                        domain="[('company_id', '=', company_id)]")
    distribution_chanel = fields.Many2one('distribution.channel', string="Kênh bán hàng")
    sale_uom = fields.Many2one('sonha.uom', string="Đơn vị tính")
    deliver_plant = fields.Many2one('sonha.plant', string="Kho xuất")
    tax = fields.Many2one('tax.classification', string="Thuế")
    aag_malt = fields.Many2one('account.assignment', string="Nhóm định khoản doanh thu")
    mat_group_1 = fields.Selection([('l2', "L2: Hàng loại 2")], string="Nhóm mặt hàng 1")
    mat_group_2 = fields.Selection([('b', "B: Hàng bộ"),
                                    ('c', "C: Hàng hóa chính"),
                                    ('p', "P: Hàng hóa phụ")], string="Nhóm mặt hàng 2")
    mat_group_price = fields.Many2one('material.price.group', string="Nhóm giá mặt hàng")
    item_category_group = fields.Many2one('item.category.group', string="Nhóm loại hàng",
                                          domain="[('sale_org', 'in', sale_organization), "
                                                 "('distb_channel', 'in', distribution_chanel), "
                                                 "('mat_type', 'in', mat_type)]")
    mat_type = fields.Many2one('x.material.type', compute="compute_material_type", store=True)
    company_id = fields.Many2one('res.company', string="Công ty", compute="get_company_id", store=True)
    md_product_id = fields.Many2one('md.product')

    @api.depends('product_code_id.product_type')
    def compute_material_type(self):
        for r in self:
            r.mat_type = r.product_code_id.product_type.id if r.product_code_id.product_type else None
            if r.product_code_id.product_type and r.product_code_id.product_type.x_code == "Z500":
                category_group = self.env['item.category.group'].sudo().search([('category_group_code', '=', "LEIS")])
                aag_malt = self.env['account.assignment'].sudo().search([('code', '=', "Z6")])
                r.item_category_group = category_group.id
                r.aag_malt = aag_malt.id
            elif r.product_code_id.product_type and r.product_code_id.product_type.x_code not in ['Z100', 'Z101', 'Z103', 'Z800']:
                aag_malt = self.env['account.assignment'].sudo().search([('code', '=', "Z4")])
                r.aag_malt = aag_malt.id
                r.item_category_group = None
            else:
                r.item_category_group = None
                r.aag_malt = None

    @api.onchange('sale_organization')
    def onchange_sale_organization(self):
        for r in self:
            if r.sale_organization and r.sale_organization.code in ['1002', '2201']:
                chanel = self.env['distribution.channel'].sudo().search([('code', '=', "XK")])
                r.distribution_chanel = chanel.id
            else:
                r.distribution_chanel = None

    @api.depends('product_code_id.plant_data.sonha_plant')
    def get_company_id(self):
        for r in self:
            if r.product_code_id.plant_data.sonha_plant:
                r.company_id = r.product_code_id.plant_data.sonha_plant.company_id.id
            else:
                r.company_id = None

