from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class BookCar(models.Model):
    _name = 'book.car'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    default=lambda self: self.default_department(), tracking=True)
    purpose = fields.Text("Mục đích sử dụng", tracking=True)
    amount_people = fields.Integer("Số người đi", tracking=True)
    phone_number = fields.Char("Số điện thoại liên hệ", tracking=True)
    start_place = fields.Text("Điểm khởi hành", tracking=True)
    end_place = fields.Text("Điểm đến", tracking=True)
    start_date = fields.Date("Ngày khởi hành", tracking=True)
    end_date = fields.Date("Ngày kết thúc", tracking=True)
    start_time = fields.Float("Thời gian khởi hành", tracking=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True)
    driver = fields.Many2one('hr.employee', string="Lái xe", tracking=True)
    driver_phone = fields.Char("Số điện thoại lái xe", tracking=True)
    license_plate = fields.Char("Biển số xe", tracking=True)
    receive_people = fields.Many2one('hr.employee', string="Người nhận thẻ", tracking=True)
    receive_time = fields.Date("Ngày trả thẻ", tracking=True)
    approve_people = fields.Many2one('hr.employee', string="Người phê duyệt",
                                     default=lambda self: self.default_approve_people(), tracking=True)
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('approved', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái", default='draft', tracking=True)
    competency_employee = fields.Many2one('hr.employee', string="Nhân viên xử lý")
    booking_employee_id = fields.Many2one('hr.employee', string="Nguời liên hệ",
                                          domain="[('department_id', '=', department_id)]", tracking=True)
    booking_employee_job_id = fields.Many2one('hr.job', string="Chức vụ người liên hệ",
                                              compute="filter_booking_employee_job", tracking=True)
    company_id = fields.Many2one('res.company', string="Công ty",
                                 default=lambda self: self.default_approve_people(), tracking=True)
    return_people = fields.Many2one('hr.employee', string="Người trả thẻ")
    type = fields.Selection([('draft', "Nháp"),
                             ('waiting', "Chờ duyệt"),
                             ('approved', "Đã duyệt"),
                             ('exist_car', "Cấp xe"),
                             ('issuing_card', "Cấp thẻ"),
                             ('cancel', "Hủy")], string="Loại", default='draft')
    status_exist_car = fields.Selection([('draft', "Nháp"),
                                         ('waiting', "Chờ duyệt"),
                                         ('approved', "Đã duyệt"),
                                         ('exist', "Cấp xe"),
                                         ('done', "Hoàn thành")], string="Trạng thái", tracking=True)
    status_issuing_card = fields.Selection([('draft', "Nháp"),
                                            ('waiting', "Chờ duyệt"),
                                            ('approved', "Đã duyệt"),
                                            ('issuing', "Cấp thẻ"),
                                            ('done', "Hoàn thành")], string="Trạng thái", tracking=True)
    list_view_status = fields.Text("Trạng thái", default="Nháp")
    reason = fields.Text("Lý do hủy", tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Người tạo đơn")

    def default_approve_people(self):
        return self.department_id.manager_id if self.department_id.manager_id else None

    def default_department(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        department_id = emp.department_id
        if department_id:
            return department_id
        else:
            return None

    def default_approve_people(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        company_id = emp.company_id
        if company_id:
            return company_id
        else:
            return None

    @api.depends('booking_employee_id.job_id')
    def filter_booking_employee_job(self):
        for r in self:
            r.booking_employee_job_id = r.booking_employee_id.job_id.id if r.booking_employee_id.job_id else None

    def action_approve(self):
        for r in self:
            if r.approve_people and r.approve_people.user_id.id == self.env.user.id:
                r.status = 'approved'
                r.type = 'approved'
                r.list_view_status = r.list_view_status + " → Đã duyệt"
                # if r.competency_employee.work_email:
                #     request_template = self.env.ref('sonha_book_car.template_mail_to_competency_employee')
                #     request_template.send_mail(r.id, force_send=True)
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
                r.status_issuing_card = 'issuing'
                r.type = 'issuing_card'
                r.list_view_status = r.list_view_status + " → Cấp thẻ"
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_not_issuing_card(self):
        for r in self:
            if r.competency_employee and r.competency_employee.user_id.id == self.env.user.id:
                return {
                    'name': 'Nhập lý do hủy đơn',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.not.issuing.card',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                    },
                }
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

    def action_exist_car_done(self):
        for r in self:
            if r.create_uid.id == self.env.user.id:
                r.status_exist_car = 'done'
                r.list_view_status = r.list_view_status + " → Hoàn thành"
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
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', res.create_uid.id)], limit=1)
        competency_employee = self.env['config.competency.employee'].sudo().search([('company_id', '=', res.company_id.id)], limit=1)
        res.sudo().write({'employee_id': emp.id if emp else None,
                          'competency_employee': competency_employee.employee_id.id if competency_employee.employee_id else None})
        return res

    def action_sent(self):
        for r in self:
            if r.create_uid.id == self.env.user.id:
                r.status = 'waiting'
                r.type = 'waiting'
                r.list_view_status = r.list_view_status + " → Chờ duyệt"
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_to_draft(self):
        for r in self:
            if r.approve_people and r.approve_people.user_id.id == self.env.user.id:
                r.status = 'draft'
                r.type = 'draft'
                r.list_view_status = "Nháp"
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

