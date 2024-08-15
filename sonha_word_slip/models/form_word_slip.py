from odoo import api, fields, models


class FormWordSlip(models.Model):
    _name = 'form.word.slip'

    employee_id = fields.Many2one('hr.employee', "Tên nhân viên")
    type = fields.Many2one('config.word.slip', "Loại đơn")
    word_slip_id = fields.One2many('word.slip', 'word_slip', string="Ngày")
    description = fields.Text("Lý do")
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái')
