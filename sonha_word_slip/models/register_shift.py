from odoo import api, fields, models


class RegisterShift(models.Model):
    _name = 'register.shift'

    employee_id = fields.Many2one('hr.employee', "Tên nhân viên")
    type_register = fields.Selection([
        ('fixed_date', 'Theo ngày cố định'),
        ('about_day', 'Theo khoảng ngày'),
    ], string='Kiểu đăng ký')
    from_date = fields.Date("Từ ngày")
    to_date = fields.Date("Đến ngày")
    register_rel = fields.One2many('register.shift.rel', 'register_shift', string="Chi tiết đăng ký ca")
    description = fields.Text("Mô tả")

    is_display = fields.Boolean("Hiển thị ngày", default=False, compute="get_show_display_date")

    #Kiểm tra xem đăng ký đổi ca theo khoảng ngày hay không
    @api.depends('type_register')
    def get_show_display_date(self):
        for r in self:
            if r.type_register == 'about_day':
                r.is_display = True
            else:
                r.is_display = False

