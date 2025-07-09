from odoo import api, fields, models


class CostCoverage(models.Model):
    _name = 'cost.coverage'

    category = fields.Text("Danh mục các chi phí được đài thọ (Công ty không phải thanh toán)")

    plan_id = fields.Many2one('plan.collaborate')

