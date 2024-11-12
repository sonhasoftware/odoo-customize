from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterOvertime(models.Model):
    _name = 'register.overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True)
    start_date = fields.Date("Từ ngày", tracking=True, required=True)
    end_date = fields.Date("Đến ngày", tracking=True, required=True)
    start_time = fields.Float("Thời gian bắt đầu", tracking=True, required=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True, required=True)
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
