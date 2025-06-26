from odoo import api, fields, models


class CostEstimated(models.Model):
    _name = 'cost.estimated'

    category = fields.Char("Danh mục chi phí công ty thanh toán")
    quantity = fields.Float("Số lượng")
    unit_price = fields.Float("Đơn giá")
    foreign_currency = fields.Float("Thành tiền ngoại tệ")
    convert = fields.Float("Mệnh giá quy đổi sang VNĐ")
    price_vnd = fields.Float("Thành tiền VNĐ")

    plan_id = fields.Many2one('plan.collaborate')

