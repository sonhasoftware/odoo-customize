from odoo import models, fields, api


class CusGroup1(models.Model):
    _name = 'cus.group.1'
    _rec_name = 'cus_group_1_name'

    sale_district = fields.Many2one('sale.district', string="Vùng kinh doanh")
    name = fields.Char("Nhóm khách hàng 1")
    cus_group_1_name = fields.Char("Tên nhóm khách hàng 1")
    province = fields.Many2one('res.country.state', string="Tỉnh thành")
