from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MDProduct(models.Model):
    _name = 'md.product'

    product_code = fields.Char("Mã vật tư")
    product_type = fields.Many2one('x.material.type', string="Loại vật tư")
    product_name = fields.Char("Tên vật tư", size=40)
    product_english_name = fields.Char("Tên vật tư tiếng anh", size=40)
    product_long_name = fields.Char("Tên đầy đủ", size=128)
    status = fields.Selection([('draft', "Nháp"), ('done', "Đã duyệt")], string="Trạng thái", default='draft')
    basic_data = fields.One2many('basic.mat.data', 'product_code_id', string="Thông tin cơ bản")
    alternative_uom = fields.One2many('alternative.uom', 'product_code_id', string="Đơn vị thay thế")
    plant_data = fields.One2many('plant.data', 'product_code_id', string="Thông tin plant")
    sale_data = fields.One2many('sales.data', 'product_code_id', string="Thông tin bán hàng")
    have_alt_uom = fields.Boolean("Đơn vị tính khác")
    is_z100 = fields.Boolean("Là thành phẩm sản xuất tại một đơn vị trong tập đoàn")
    is_z101 = fields.Boolean("Là bán thành phẩm sản xuất tại một đơn vị trong tập đoàn")
    is_z102 = fields.Boolean("Là thành phẩm sản xuất tại một đơn vị trong tập đoàn loại 2")

    @api.onchange('is_z100', 'is_z101', 'is_z102')
    def filter_product_type(self):
        for r in self:
            if r.is_z100:
                code = "Z100"
                r.is_z101 = False
                r.is_z102 = False
            if r.is_z101:
                code = "Z101"
                r.is_z100 = False
                r.is_z102 = False
            if r.is_z102:
                code = "Z102"
                r.is_z101 = False
                r.is_z100 = False
            if r.is_z100 or r.is_z101 or r.is_z102:
                product_type = self.env['x.material.type'].sudo().search([('x_code', '=', code)])
                r.product_type = product_type.id if product_type else None
            else:
                r.product_type = None

    def unlink(self):
        for r in self:
            self.env['basic.mat.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['alternative.uom'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['plant.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['sales.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
        return super(MDProduct, self).unlink()

    def action_approve(self):
        for r in self:
            r.status = 'done'






