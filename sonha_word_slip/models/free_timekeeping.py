from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


class FreeTimekeeping(models.Model):
    _name = 'free.timekeeping'
    _description = 'Free Timekeeping'

    employee_id = fields.Many2one('hr.employee', "Nhân viên", store=True, required=True)
    start_date = fields.Date("Ngày bắt đầu", store=True, required=True)
    end_date = fields.Date("Ngày kết thúc", store=True, required=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('active', 'Hoạt động'),
        ('unactive', 'Ngừng hoạt động'),
    ], string="Trạng thái", store=True, default='draft', readonly=True)

    def multi_approval(self):
        for r in self:
            r.state = 'active'

    def multi_draft(self):
        for r in self:
            r.state = 'draft'

    def multi_de_active(self):
        for r in self:
            r.state = 'unactive'
