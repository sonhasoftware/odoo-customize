from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
from odoo.exceptions import UserError, ValidationError


class RelLamThem(models.Model):
    _name = 'rel.lam.them'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)
    company_id = fields.Many2one('res.company', string="Công ty", store=True)
    date = fields.Date(string="Ngày", store=True)
    start_time = fields.Float(string="Thời gian bắt đầu", store=True)
    end_time = fields.Float(string="Thời gian kết thúc", store=True)
    time_amount = fields.Float(string="Thời gian làm thêm", store=True)

    key = fields.Many2one('overtime.rel', string="Key ngày", store=True)
    key_form = fields.Many2one('register.overtime.update', string="Key", store=True)

    type = fields.Selection([
        ('one', 'Tạo cho tôi'),
        ('many', 'Tạo hộ')
    ], string="Loại đăng ký", store=True)

    status = fields.Selection([
        ('draft', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', store=True)

    status_lv2 = fields.Selection([
        ('draft', 'Nháp'),
        ('waiting', 'Chờ duyệt'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', store=True)