from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class WordSlip(models.Model):
    _name = 'word.slip'

    from_date = fields.Date("Từ ngày")
    to_date = fields.Date("Đến ngày")

    start_time = fields.Selection([
        ('first_half', 'Nửa ca đầu'),
        ('second_half', 'Nửa ca sau'),
    ], string='Ca bắt đầu')

    end_time = fields.Selection([
        ('first_half', 'Nửa ca đầu'),
        ('second_half', 'Nửa ca sau'),
    ], string='Ca kết thúc')

    time_to = fields.Float("Thời gian bắt đầu")
    time_from = fields.Float("Thời gian kết thúc")

    word_slip = fields.Many2one('form.word.slip')
    employee_id = fields.Many2one('hr.employee', related='word_slip.employee_id')
    type = fields.Many2one('config.word.slip', related='word_slip.type')
    duration = fields.Float("Ngày", compute="get_duration")
    reason = fields.Text(string="Lý do")

    #Lấy thông tin số ngày công mà nhân viên nghỉ
    @api.depends('start_time', 'end_time', 'from_date', 'to_date')
    def get_duration(self):
        for r in self:
            r.duration = 0
            if r.from_date == r.to_date:
                if r.type.date_and_time == 'date':
                    if r.start_time and r.end_time:
                        if r.start_time == r.end_time:
                            r.duration = 0.5
                        elif r.start_time == 'first_half' and r.end_time == 'second_half':
                            r.duration = 1
            else:
                start_date = fields.Date.from_string(r.from_date)
                end_date = fields.Date.from_string(r.to_date)
                day_duration = (end_date - start_date).days + 1
                if r.type.date_and_time == 'date':
                    if r.start_time and r.end_time:
                        if r.start_time == r.end_time:
                            r.duration = 0.5 * day_duration
                        elif r.start_time == 'first_half' and r.end_time == 'second_half':
                            r.duration = 1 * day_duration

    @api.constrains('from_date', 'to_date', 'employee_id')
    def _check_date_overlap(self):
        for record in self:
            if record.from_date > record.to_date:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")

            # Tìm các bản ghi khác của cùng một nhân viên
            overlapping_slips = self.env['word.slip'].search([
                ('id', '!=', record.id),  # Loại trừ chính bản ghi hiện tại
                ('employee_id', '=', record.employee_id.id),
                ('from_date', '<=', record.to_date),
                ('to_date', '>=', record.from_date),
            ])

            if overlapping_slips:
                if record.type.date_and_time == 'date':
                    for slip in overlapping_slips:
                        if record.start_time == 'second_half' and record.end_time == 'first_half':
                            raise ValidationError("Ca bắt đầu không thể sau ca kết thúc.")

                        if overlapping_slips.type.date_and_time == 'date':
                            if slip.start_time != slip.end_time or record.start_time != record.end_time:
                                raise ValidationError("Bạn bị trùng ca với đơn khác của bạn.")
                            else:
                                if slip.start_time == record.start_time:
                                    raise ValidationError("Bạn bị trùng ca với đơn khác của bạn.")
                else:
                    for slip in overlapping_slips:
                        if record.time_to > record.time_from:
                            raise ValidationError("Thời gian bắt đầu phải trước thời gian kết thúc.")

                        if overlapping_slips.type.date_and_time == 'time':
                            if not (record.time_to >= slip.time_from or record.time_from <= slip.time_to):
                                raise ValidationError("Bạn bị trùng khoảng thời gian với đơn khác của bạn.")
