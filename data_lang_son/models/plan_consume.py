from odoo import api, fields, models


class PlanConsume(models.Model):
    _name = 'plan.consume'

    month = fields.Integer("Tháng")
    year = fields.Integer("Năm")
    plan_consume = fields.One2many('plan.consume.rel', 'plan_id', string="Chi tiết")
