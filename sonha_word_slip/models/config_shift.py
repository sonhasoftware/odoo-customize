from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import timedelta
class ConfigShift(models.Model):
    _name = 'config.shift'
    _order = "code"
    _rec_name = 'name_code_shift'

    code = fields.Char("Mã ca")
    name = fields.Char("Tên ca")
    earliest = fields.Integer("Sớm nhất được vào")
    overtime_before_shift = fields.Integer("Làm Thêm Trước Ca")
    start = fields.Datetime("Bắt đầu ca")
    late_entry_allowed = fields.Integer("Cho Phép Vào Muộn")
    latest = fields.Integer("Muộn Nhất Phải Vào")
    rest = fields.Integer("Nghỉ")
    from_rest = fields.Datetime("Nghỉ từ")
    minutes_rest = fields.Integer("Số phút nghỉ", compute="_compute_minutes_rest", store=True)
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
    company_id = fields.Many2many('res.company', 'ir_employee_shift_rel',
                                 'employee_shift_rel', 'shift_rel', string="Công ty", required=True)
    is_office_hour = fields.Boolean(string="Hành chính")

    night = fields.Boolean("Check ca ngày/đêm", default=False, compute="check_shift_night")

    c2k3 = fields.Boolean("Ca 2 kíp 3")
    c3k4 = fields.Boolean("Ca 3 kíp 4")
    half_shift = fields.Boolean("Nửa ca", default=False)
    shift_toxic = fields.Boolean("Ca độc hại")
    shift_ot = fields.Boolean("Làm thêm")
    type_shift = fields.Selection([
        ('hc', 'Hành chính'),
        ('sp', 'Sản phẩm'),
    ], string="Loại ca")

    type_ot = fields.Selection([
        ('hour', 'Giờ'),
        ('nb', 'Nghỉ bù'),
    ], string="Làm thêm hưởng")

    coefficient = fields.Float("Hệ số", default=1)
    recent_work = fields.Float("Công hưởng %", default=1)
    key = fields.Char("Ký hiệu ca")

    #Kiểm tra xem ca có phải ca đêm hay không
    @api.depends('start', 'end_shift')
    def check_shift_night(self):
        for r in self:
            if r.end_shift and r.start and (r.end_shift + timedelta(hours=7)).time() < (r.start + timedelta(hours=7)).time():
                r.night = True
            else:
                r.night = False

    @api.depends('from_rest', 'to_rest')
    def _compute_minutes_rest(self):
        for r in self:
            if r.from_rest and r.to_rest:
                diff = (r.to_rest - r.from_rest).total_seconds()
                
                # Check for lazy overnight shift on the SAME calendar day
                if diff < 0 and r.to_rest.date() == r.from_rest.date():
                    diff += 24 * 3600
                    
                r.minutes_rest = max(0, int(diff / 60))
            else:
                r.minutes_rest = 0

    @api.constrains('from_rest', 'to_rest')
    def _check_rest_time(self):
        for r in self:
            if r.from_rest and r.to_rest:
                # Nếu Nghỉ đến nằm ở ngày hôm trước so với Nghỉ từ, chắc chắn là lỗi nhập sai
                if r.to_rest.date() < r.from_rest.date():
                    raise ValidationError("Thời gian 'Nghỉ đến' không hợp lệ! Bạn không thể chọn ngày kết thúc nằm trước ngày bắt đầu.")
                
                # Nếu cùng một ngày nhưng Nghỉ đến < Nghỉ từ (người dùng nhập lười ca đêm), 
                # thì được phép (compute sẽ tự cộng 24h).
                # Còn nếu khác ngày (Nghỉ đến > Nghỉ từ) thì bình thường.
                # Do đó chỉ cần chặn r.to_rest.date() < r.from_rest.date() là đủ để bắt các case ngày quá khứ.

    name_code_shift = fields.Char(string="Tên và mã ca",compute="_compute_name_code_shift",tracking=True,store=True)

    @api.depends('name','code')
    def _compute_name_code_shift(self):
        for r in self:
            if r.name and r.code:
                r.name_code_shift = r.name + ' (' + r.code + ')'
            elif r.name:
                r.name_code_shift = r.name
            elif r.code:
                r.name_code_shift = r.code
            else:
                r.name_code_shift = None