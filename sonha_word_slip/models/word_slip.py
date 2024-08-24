from odoo import api, fields, models


class WordSlip(models.Model):
    _name = 'word.slip'

    from_date = fields.Date("Từ ngày")
    to_date = fields.Date("Đến ngày")
    level = fields.Selection([
        ('full_day', '1 ngày'),
        ('half_day', 'Nửa ngày'),
    ], string='Chọn thời gian')

    word_slip = fields.Many2one('form.word.slip')
    employee_id = fields.Many2one('hr.employee', related='word_slip.employee_id')
    type = fields.Many2one('config.word.slip', related='word_slip.type')

