from odoo import api, fields, models


class TonPhep(models.Model):
    _name = 'ton.phep'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    ton = fields.Integer(string="Phép tồn", store=True)

    form_word_slip = fields.Many2one('form.word.slip', string="Key", store=True)
    key_form_char = fields.Char(string="Key", store=True)

    is_temp = fields.Boolean(string="Check", store=True)
