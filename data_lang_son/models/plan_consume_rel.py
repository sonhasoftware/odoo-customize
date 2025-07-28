from odoo import api, fields, models


class PlanConsumeRel(models.Model):
    _name = 'plan.consume.rel'

    plan_id = fields.Many2one('plan.consume')
    branch = fields.Many2one('config.pumping')
    plan_consume_electric = fields.Integer("Kế hoạch tiêu thụ điện")
    plan_consume_water = fields.Integer("Kế hoạch tiêu thụ nước")
    revenue = fields.Integer("Doanh thu")
    loss_rate = fields.Float("% tỷ lệ hao hụt")
    no_name = fields.Char("Chưa đặt tên")
