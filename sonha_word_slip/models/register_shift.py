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
        self.explode_to_shift(res)
        return res

    def write(self, vals):
        res = super(RegisterShift, self).write(vals)
        for rec in self:
            self.explode_to_shift(rec)
        return res

    def unlink(self):
        for r in self:
            self.env['rel.ca'].sudo().search([('key_form', '=', r.id), ('type', '=', 'doi_ca')]).unlink()
        return super(RegisterShift, self).unlink()

    def explode_to_shift(self, register_shift=None):
        model = self.env['rel.ca'].sudo()
        for r in register_shift.register_rel:
            model.search([('key', '=', r.id), ('type', '=', 'doi_ca')]).unlink()
        query = """INSERT INTO rel_ca(employee_id, department_id, company_id, date, shift_id, key, key_form, type)
                            SELECT
                                rs.employee_id AS employee_id,
                                rs.department_id AS department_id,
                                rsr.company_id AS company_id,
                                rsr.date::date AS date,
                                rsr.shift AS shift_id,
                                rsr.id AS key,
                                rsr.register_shift AS key_form,
                                'doi_ca' AS type
                            FROM (
                                SELECT *
                                FROM register_shift_rel
                                WHERE register_shift = %(register_shift)s
                            ) rsr
                            JOIN register_shift rs ON rsr.register_shift = rs.id
                            WHERE rsr.shift IS NOT NULL
                            AND rsr.date IS NOT NULL
                            AND rsr.company_id IS NOT NULL;"""
        self.env.cr.execute(query, {'register_shift': register_shift.id})


