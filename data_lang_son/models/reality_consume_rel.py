from odoo import api, fields, models


class RealityConsumeRel(models.Model):
    _name = 'reality.consume.rel'

    reality_id = fields.Many2one('reality.consume')
    date = fields.Date("Ngày")
    reality_consume_electric = fields.Integer("Thực tế tiêu thụ điện")
    reality_consume_water = fields.Integer("Thực tế tiêu thụ nước")
    revenue = fields.Integer("Doanh thu")
    loss_rate = fields.Float("% tỷ lệ hao hụt")
    no_name = fields.Char("Chưa đặt tên")
