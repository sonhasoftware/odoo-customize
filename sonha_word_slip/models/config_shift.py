from odoo import api, fields, models


class ConfigShift(models.Model):
    _name = 'config.shift'

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
