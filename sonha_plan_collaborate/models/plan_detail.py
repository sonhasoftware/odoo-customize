from odoo import api, fields, models


class PlanDetail(models.Model):
    _name = 'plan.detail'

    time = fields.Date("Thời gian")
    location = fields.Char("Địa đỉểm")
    content = fields.Text("Nội dung công việc")

    plan_id = fields.Many2one('plan.collaborate')

