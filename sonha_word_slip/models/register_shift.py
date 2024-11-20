from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShift(models.Model):
    _name = 'register.shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2one('hr.employee', "Tên nhân viên", tracking=True, required=True)
    type_register = fields.Selection([
        ('fixed_date', 'Theo ngày cố định'),
        ('about_day', 'Theo khoảng ngày'),
    ], string='Kiểu đăng ký', tracking=True)
    from_date = fields.Date("Từ ngày", tracking=True)
    to_date = fields.Date("Đến ngày", tracking=True)
    register_rel = fields.One2many('register.shift.rel', 'register_shift', string="Chi tiết đăng ký ca", tracking=True)
    description = fields.Text("Mô tả", tracking=True)

    is_display = fields.Boolean("Hiển thị ngày", default=False, compute="get_show_display_date")
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    #Kiểm tra xem đăng ký đổi ca theo khoảng ngày hay không
    @api.depends('type_register')
    def get_show_display_date(self):
        for r in self:
            if r.type_register == 'about_day':
                r.is_display = True
            else:
                r.is_display = False

    def action_confirm(self):
        for r in self:
            if r.employee_id.parent_id.user_id.id == self.env.user.id:
                r.status = 'done'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    @api.constrains('register_rel')
    def check_register_rel(self):
        if not self.register_rel:
            raise ValidationError("Hãy thêm thông tin chi tiết về ca mà bạn muốn đăng ký")