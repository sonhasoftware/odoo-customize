from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SalesData(models.Model):
    _name = 'sales.data'

    product_code_id = fields.Many2one('md.product', string="Mã vật tư")
    sale_organization = fields.Many2one('sale.organization', string="Tổ chức bán hàng")
    distribution_chanel = fields.Many2one('distribution.channel', string="Kênh bán hàng")
    sale_unit = fields.Many2one('uom.uom', string="Đơn vị tính bán hàng")
    deliver_warehouse = fields.Many2one('stock.warehouse', string="Kho xuất")
    tax = fields.Many2one('tax.classification', string="Thuế")
    aag_malt = fields.Many2one('account.assignment', string="Nhóm định khoản doanh thu")
    mat_group_1 = fields.Selection([('l2', "L2: Hàng loại 2")], string="Nhóm mặt hàng 1")
    mat_group_2 = fields.Selection([('b', "B: Hàng bộ"),
                                    ('c', "C: Hàng hóa chính"),
                                    ('p', "L2: Hàng hóa phụ")], string="Nhóm mặt hàng 2")
    mat_group_price = fields.Many2one('material.price.group', string="Nhóm giá mặt hàng")
    item_category_group = fields.Many2one('item.category.group', string="Nhóm loại hàng")