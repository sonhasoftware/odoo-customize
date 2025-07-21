from odoo import api, fields, models


class StepByStep(models.Model):
    _name = 'step.step'

    stt = fields.Integer("Số Thứ tự")
    status = fields.Char("Trạng thái")
    approval = fields.Selection([
        ('qlc1', 'Quản lý cấp 1'),
        ('qlc2', 'Quản lý cấp 2'),
        ('hr', 'Nhân sự(HR)'),
        ('gd', 'Giám đốc'),
        ('qlc3', 'Quản lý cấp 3'),
    ], string="Người duyệt")
    employee_approval = fields.Many2one('hr.employee', string="Người duyệt")

    config_approval = fields.Many2one('config.approval')

    plan_id = fields.Many2one('plan.collaborate', string="...")



