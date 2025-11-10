from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
from odoo.exceptions import UserError, ValidationError


class RelDonTu(models.Model):
    _name = 'rel.don.tu'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    date = fields.Date("Ngày", store=True)
    leave_more = fields.Float("Phép thêm", store=True)
    leave = fields.Float("Số ngày nghỉ phép", store=True)
    type_leave = fields.Many2one('config.word.slip', string="Loại đơn", store=True)
    key_type_leave = fields.Char(related='type_leave.key', string="Key loại đơn", store=True)
    key = fields.Many2one('word.slip', string="Key ngày", store=True)
    key_char = fields.Char(string="Key", store=True)

    key_form = fields.Many2one('form.word.slip', string="Key", store=True)
    key_form_char = fields.Char(string="Key", store=True)

    is_temp = fields.Boolean(string="Check", store=True)
