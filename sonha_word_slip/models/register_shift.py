from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RegisterShift(models.Model):
    _name = 'register.shift'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
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

    def create(self, vals):
        res = super(RegisterShift, self).create(vals)
        self.explode_to_shift(res.employee_id, res.register_rel)
        return res

    def write(self, vals):
        res = super(RegisterShift, self).write(vals)
        for rec in self:
            self.explode_to_shift(rec.employee_id, rec.register_rel)
        return res

    def unlink(self):
        for r in self:
            self.env['rel.ca'].sudo().search([('key_register_shift', '=', r.id)]).unlink()
        return super(RegisterShift, self).unlink()

    def explode_to_shift(self, employee_id=None, register_rel=None):
        model = self.env['rel.ca'].sudo()

        if not register_rel or not employee_id:
            return

        for r in register_rel:
            if not r.date or not r.shift or not r.company_id:
                continue

            model.search([('key', '=', r.id)]).unlink()

            model.create({
                'employee_id': employee_id.id,
                'department_id': r.register_shift.department_id.id,
                'company_id': r.company_id.id,
                'date': r.date,
                'shift_id': r.shift.id,
                'key': r.id,
                'key_register_shift': r.register_shift.id
            })


