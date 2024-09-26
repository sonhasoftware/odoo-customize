from odoo import api, fields, models


class RegisterOvertime(models.Model):
    _name = 'register.overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True)
    start_date = fields.Date("Từ ngày", tracking=True)
    end_date = fields.Date("Đến ngày", tracking=True)
    start_time = fields.Float("Thời gian bắt đầu", tracking=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True)
