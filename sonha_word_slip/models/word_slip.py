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

    @api.depends('start_time', 'end_time')
    def get_duration(self):
        for r in self:
            if r.start_time and r.end_time:
                if r.start_time == r.end_time:
                    r.duration = 0.5
                elif r.start_time == 'first_half' and r.end_time == 'second_half':
                    r.duration = 1
                else:
                    r.duration = 0
            else:
                r.duration = 0
