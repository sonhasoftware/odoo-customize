from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class OvertimeRel(models.Model):
    _name = 'overtime.rel'

    date = fields.Date("Ngày", required=True)
    start_time = fields.Float("Thời gian bắt đầu", required=True)
    end_time = fields.Float("Thời gian kết thúc", required=True)
    coefficient = fields.Float("Hệ số", default=1)
    overtime_id = fields.Many2one('register.overtime.update')
