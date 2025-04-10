from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BookCar(models.Model):
    _name = 'book.car'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", tracking=True)
    purpose = fields.Text("Mục đích sử dụng", tracking=True)
    amount_people = fields.Integer("Số người đi", tracking=True)
    phone_number = fields.Char("Số điện thoại liên hệ", tracking=True)
    start_place = fields.Text("Điểm khởi hành", tracking=True)
    end_place = fields.Text("Điểm đến", tracking=True)
    start_date = fields.Date("Ngày khởi hành", tracking=True)
    end_date = fields.Date("Ngày kết thúc", tracking=True)
    start_time = fields.Float("Thời gian khởi hành", tracking=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True)
    driver = fields.Char("Lái xe", tracking=True)
    driver_phone = fields.Char("Số điện thoại lái xe", tracking=True)
    license_plate = fields.Char("Biển số xe", tracking=True)
    receive_people = fields.Many2one('hr.employee', string="Người nhận thẻ", tracking=True)
    receive_time = fields.Date("Ngày trả thẻ", tracking=True)
    approve_people = fields.Many2one('hr.employee', string="Người phê duyệt", tracking=True)
    status = fields.Selection([('draft', "Nháp"),
                               ('approved', "Đã duyệt"),
                               ('issuing', "Cấp thẻ"),
                               ('done', "Hoàn thành"),
                               ('cancel', "Hủy")], string="Trạng thái", default='draft', tracking=True)
    exist_car = fields.Boolean("Còn xe")
    issuing_card = fields.Boolean("Cấp thẻ")
    competency_employee = fields.Many2one('hr.employee', string="Nhân viên xử lý", compute="filter_competency_employee")

    @api.depends('department_id')
    def filter_competency_employee(self):
        for r in self:
            if r.department_id:
                competency_employee = self.env['config.competency.employee'].sudo().search([('company_id', '=', r.department_id.company_id.id)], limit=1)
                r.competency_employee = competency_employee.employee_id.id if competency_employee else None
            else:
                r.competency_employee = None

    def action_approve(self):
        for r in self:
            if r.approve_people and r.approve_people.user_id.id == self.env.user.id:
                r.status = 'approved'
                if r.competency_employee.work_email:
                    request_template = self.env.ref('sonha_book_car.template_mail_to_competency_employee')
                    request_template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_exist_car(self):
        for r in self:
            if r.competency_employee and r.competency_employee.user_id.id == self.env.user.id:
                return {
                    'name': 'Nhập thông tin xe',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.exist.car',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                    },
                }
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_issuing_card(self):
        for r in self:
            if r.competency_employee and r.competency_employee.user_id.id == self.env.user.id:
                r.status = 'issuing'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_not_issuing_card(self):
        for r in self:
            if r.competency_employee and r.competency_employee.user_id.id == self.env.user.id:
                r.status = 'cancel'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_return_card(self):
        for r in self:
            if r.create_uid.id == self.env.user.id:
                return {
                    'name': 'Nhập thông trả thẻ',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.return.card',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                    },
                }
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    # def unlink(self):
    #     for r in self:
    #         if r.status != 'draft':
    #             raise ValidationError("Chỉ được xóa khi trạng thái là nháp!")
    #         else:
    #             pass
    #     return super(BookCar, self).unlink()

    def create(self, vals):
        res = super(BookCar, self).create(vals)
        if res.approve_people and res.approve_people.work_email:
            template = self.env.ref('sonha_book_car.template_mail_booking_car')
            template.send_mail(res.id, force_send=True)
        return res
