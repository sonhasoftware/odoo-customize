from odoo import api, fields, models
from datetime import timedelta


class ConfigShift(models.Model):
    _name = 'config.shift'
    _order = "code"
    _rec_name = 'code'

    code = fields.Char("Mã ca")
    name = fields.Char("Tên ca")
    earliest = fields.Integer("Sớm nhất được vào")
    overtime_before_shift = fields.Integer("Làm Thêm Trước Ca")
    start = fields.Datetime("Bắt đầu ca")
    late_entry_allowed = fields.Integer("Cho Phép Vào Muộn")
    latest = fields.Integer("Muộn Nhất Phải Vào")
    rest = fields.Integer("Nghỉ")
    from_rest = fields.Datetime("Nghỉ từ")
    minutes_rest = fields.Integer("Số phút nghỉ")
    to_rest = fields.Datetime("Nghỉ đến")
    earliest_out = fields.Integer("Sớm nhất được ra")
    allow_early_exit = fields.Integer("Cho Phép Ra Sớm")
    end_shift = fields.Datetime("Hết ca")
    overtime_after_shift = fields.Integer("Làm thêm sau ca")
    latest_out = fields.Integer("Muộn Nhất Phải ra")
    night_shift = fields.Integer("Ca đêm")
    night_shift_from = fields.Datetime("Ca đêm từ")
    night_shift_to = fields.Datetime("Ca đêm đến")
    effect_from = fields.Date("Hiệu lực từ")
    effect_to = fields.Date("Hiệu lực đến")
    using = fields.Integer("Dùng")
    note = fields.Char("Ghi chú")
    contract = fields.Integer("Ca khoán")
    company_id = fields.Many2one('res.company', string="Công ty")
    is_office_hour = fields.Boolean(string="Hành chính")

    night = fields.Boolean("Check ca ngày/đêm", default=False, compute="check_shift_night")

    #Kiểm tra xem ca có phải ca đêm hay không
    @api.depends('start', 'end_shift')
    def check_shift_night(self):
        for r in self:
            if (r.end_shift + timedelta(hours=7)).time() < (r.start + timedelta(hours=7)).time():
                r.night = True
            else:
                r.night = False
