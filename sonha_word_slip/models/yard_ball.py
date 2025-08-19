from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class YardBall(models.Model):
    _name = 'yard.ball'

    area = fields.Many2one('sonha.area', string="Khu vực")
    yard = fields.Many2one('sonha.yard', string="Sân")
    date_active = fields.Date("Ngày hoạt động")
    start_active = fields.Float("Thời gian hoạt động từ")
    end_active = fields.Float("Thời gian hoạt động đến")
    pick_up = fields.Boolean("Nhặt bóng")
    start_ball = fields.Float("Từ")
    end_ball = fields.Float("Đến")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
