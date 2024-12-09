from odoo import api, fields, models


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
