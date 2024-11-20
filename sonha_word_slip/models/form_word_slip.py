from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FormWordSlip(models.Model):
    _name = 'form.word.slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True)
    type = fields.Many2one('config.word.slip', "Loại đơn", tracking=True, required=True)
    word_slip_id = fields.One2many('word.slip', 'word_slip', string="Ngày", tracking=True)
    description = fields.Text("Lý do", tracking=True)
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    def action_confirm(self):
        for r in self:
            if r.employee_id.parent_id.user_id.id == self.env.user.id:
                r.status = 'done'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    @api.constrains('word_slip_id')
    def check_word_slip_id(self):
        if not self.word_slip_id:
            raise ValidationError(f"Đơn từ của bạn chưa chọn thời gian")