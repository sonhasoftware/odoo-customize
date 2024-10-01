from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterOvertime(models.Model):
    _name = 'register.overtime'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
    start_time = fields.Float("Thời gian bắt đầu")
    end_time = fields.Float("Thời gian kết thúc")
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
