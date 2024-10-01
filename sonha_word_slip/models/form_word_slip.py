from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    def action_confirm(self):
        for r in self:
            if r.employee_id.parent_id.id == self.env.user.id:
                r.status = 'done'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")
