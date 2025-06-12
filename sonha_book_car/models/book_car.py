from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta


class BookCar(models.Model):
    _name = 'book.car'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    default=lambda self: self.default_department(), required=True, tracking=True)
    purpose = fields.Text("Mục đích sử dụng", required=True, tracking=True)
    amount_people = fields.Integer("Số người đi", tracking=True)
    phone_number = fields.Char("Số điện thoại liên hệ", required=True, tracking=True)
    start_place = fields.Text("Điểm khởi hành", required=True, tracking=True)
    end_place = fields.Text("Điểm đến", required=True, tracking=True)
    start_date = fields.Date("Ngày khởi hành", required=True, tracking=True)
    end_date = fields.Date("Ngày kết thúc", required=True, tracking=True)
    start_time = fields.Float("Thời gian khởi hành", required=True, tracking=True)
    end_time = fields.Float("Thời gian kết thúc", required=True, tracking=True)
    driver = fields.Many2one('hr.employee', string="Lái xe", tracking=True)
    driver_phone = fields.Char("Số điện thoại lái xe", tracking=True)
    license_plate = fields.Char("Biển số xe", tracking=True)
    receive_time = fields.Date("Ngày trả thẻ", tracking=True)
    approve_people = fields.Many2one('hr.employee', string="Người phê duyệt",
                                     domain="[('company_id', '=', company_id),('user_id', '!=', uid)]",
                                     default=lambda self: self.default_approve_people(), required=True, tracking=True)
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('approved', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái", default='draft', tracking=True)
    competency_employee = fields.Many2one('hr.employee', string="Nhân viên xử lý")
    booking_employee_id = fields.Many2one('hr.employee', string="Nguời liên hệ",
                                          default=lambda self: self.default_booking_employee_id(), required=True,
                                          domain="[('department_id', '=', department_id)]", tracking=True)
    booking_employee_job_id = fields.Many2one('hr.job', string="Chức vụ người liên hệ",
                                              compute="filter_booking_employee_job", tracking=True)
    company_id = fields.Many2one('res.company', string="Công ty",
                                 default=lambda self: self.default_company_id(), required=True, tracking=True)
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
                                         ('done', "Hoàn thành")],
                                        string="Trạng thái", default='approved', tracking=True)
    status_issuing_card = fields.Selection([('draft', "Nháp"),
                                            ('waiting', "Chờ duyệt"),
                                            ('approved', "Đã duyệt"),
                                            ('issuing', "Cấp thẻ"),
                                            ('done', "Hoàn thành")],
                                           string="Trạng thái", default='approved', tracking=True)
    list_view_status = fields.Text("Trạng thái", default="Nháp")
    reason = fields.Text("Lý do hủy", tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Người tạo đơn")
    approve_people_job_id = fields.Many2one('hr.job', string="Chức vụ người phê duyệt",
                                            compute="filter_approve_people_job")
    reality_start_date = fields.Date("Ngày khởi hành thực tế", tracking=True)
    reality_end_date = fields.Date("Ngày kết thúc thực tế", tracking=True)
    check_sent = fields.Boolean("check_sent", compute="get_check_sent")
    check_approve = fields.Boolean("check_approve", compute="get_check_approve")
    check_process = fields.Boolean("check_process", compute="get_check_process")
    check_exist_car = fields.Boolean("check_exist_car", compute="get_check_exist_car")
    check_return_card = fields.Boolean("check_return_card", compute="get_check_return_card")

    @api.onchange('booking_employee_id')
    def onchange_phone_number(self):
        for r in self:
            if r.booking_employee_id.sonha_number_phone:
                r.phone_number = r.booking_employee_id.sonha_number_phone
            else:
                r.phone_number = ''

    @api.onchange('driver')
    def onchange_driver_phone(self):
        for r in self:
            if r.driver.sonha_number_phone:
                r.driver_phone = r.booking_employee_id.sonha_number_phone
            else:
                r.driver_phone = ''

    @api.onchange('department_id')
    def onchange_approve_people(self):
        for r in self:
            r.approve_people = r.department_id.manager_id.id if r.department_id.manager_id else None

    @api.depends('status', 'employee_id')
    def get_check_sent(self):
        for r in self:
            if r.status == 'draft' and (self.env.user.employee_id.id == r.employee_id.id or self.env.user.has_group('sonha_book_car.group_book_car_manager')):
                r.check_sent = True
            else:
                r.check_sent = False

    @api.depends('status', 'approve_people')
    def get_check_approve(self):
        for r in self:
            if r.status == 'waiting' and (self.env.user.employee_id.id == r.approve_people.id or self.env.user.has_group('sonha_book_car.group_book_car_manager')):
                r.check_approve = True
            else:
                r.check_approve = False

    @api.depends('type', 'competency_employee')
    def get_check_process(self):
        for r in self:
            if r.type == 'approved' and (self.env.user.employee_id.id == r.competency_employee.id or self.env.user.has_group('sonha_book_car.group_book_car_manager')):
                r.check_process = True
            else:
                r.check_process = False

    @api.depends('status_exist_car', 'competency_employee')
    def get_check_exist_car(self):
        for r in self:
            if r.status_exist_car == 'exist' and (self.env.user.employee_id.id == r.competency_employee.id or self.env.user.has_group('sonha_book_car.group_book_car_manager')):
                r.check_exist_car = True
            else:
                r.check_exist_car = False

    @api.depends('status_issuing_card', 'competency_employee')
    def get_check_return_card(self):
        for r in self:
            if r.status_issuing_card == 'issuing' and (self.env.user.employee_id.id == r.competency_employee.id or self.env.user.has_group('sonha_book_car.group_book_car_manager')):
                r.check_return_card = True
            else:
                r.check_return_card = False

    def default_booking_employee_id(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        if emp:
            return emp
        else:
            return None

    def default_approve_people(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        employee = emp.department_id.manager_id
        if employee:
            return employee
        else:
            return None

    def default_department(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        department_id = emp.department_id
        if department_id:
            return department_id
        else:
            return None

    def default_company_id(self):
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

    @api.depends('approve_people.job_id')
    def filter_approve_people_job(self):
        for r in self:
            r.approve_people_job_id = r.approve_people.job_id.id if r.approve_people.job_id else None

    def action_approve(self):
        for r in self:
            if (r.approve_people and r.approve_people.user_id.id == self.env.user.id) or self.env.user.id == 2:
                r.status = 'approved'
                r.type = 'approved'
                r.list_view_status = r.list_view_status + " → Đã duyệt"
                if r.competency_employee.work_email:
                    request_template = self.env.ref('sonha_book_car.template_mail_to_competency_employee')
                    request_template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_exist_car(self):
        for r in self:
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
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
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
                r.status_issuing_card = 'issuing'
                r.type = 'issuing_card'
                r.list_view_status = r.list_view_status + " → Cấp thẻ"
                if r.booking_employee_id.work_email:
                    request_template = self.env.ref('sonha_book_car.template_mail_accept_to_creator')
                    request_template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_not_issuing_card(self):
        for r in self:
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
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
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
                return {
                    'name': 'Nhập thông tin trả thẻ',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.return.card',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                        'default_return_people': r.booking_employee_id.id,
                        'default_department_id': r.department_id.id,
                    },
                }
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_exist_car_done(self):
        for r in self:
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
                return {
                    'name': 'Nhập thông tin xác nhận hoàn thành',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.exist.car.done',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                        'default_driver': r.driver.id,
                        'default_driver_phone': r.driver_phone,
                        'default_license_plate': r.license_plate,
                        'default_reality_start_date': r.start_date,
                        'default_reality_end_date': r.end_date,
                    },
                }
                pass
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def unlink(self):
        for r in self:
            if r.status == 'draft' or self.env.user.id == 2:
                if r.employee_id.user_id.id == self.env.user.id or self.env.user.id == 2:
                    pass
                else:
                    raise ValidationError("Chỉ được xóa khi là người tạo đơn!")
            else:
                raise ValidationError("Chỉ được xóa khi là ở trạng thái nháp!")
        return super(BookCar, self).unlink()

    def create(self, vals):
        res = super(BookCar, self).create(vals)
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', res.create_uid.id)], limit=1)
        competency_employee = self.env['config.competency.employee'].sudo().search([('company_id', '=', res.company_id.id)], limit=1)
        res.sudo().write({'employee_id': emp.id if emp else None,
                          'competency_employee': competency_employee.employee_id.id if competency_employee.employee_id else None})
        return res

    def action_sent(self):
        for r in self:
            if r.create_uid.id == self.env.user.id or self.env.user.id == 2:
                r.status = 'waiting'
                r.type = 'waiting'
                r.list_view_status = r.list_view_status + " → Chờ duyệt"
                if r.approve_people.work_email:
                    request_template = self.env.ref('sonha_book_car.template_mail_booking_car')
                    request_template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def action_to_draft(self):
        for r in self:
            if (r.approve_people and r.approve_people.user_id.id == self.env.user.id) or self.env.user.id == 2:
                r.status = 'draft'
                r.type = 'draft'
                r.list_view_status = "Nháp"
                if r.booking_employee_id.work_email:
                    request_template = self.env.ref('sonha_book_car.template_mail_book_car_to_draft')
                    request_template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    @api.constrains('start_date', 'end_date', 'start_time', 'end_time')
    def validate_date_time(self):
        for r in self:
            now = datetime.now().date()
            # if r.start_date < now:
            #     raise ValidationError("Ngày khởi hành phải lớn hơn hoặc bằng ngày hiện tại!")
            if r.start_date > r.end_date:
                raise ValidationError("Ngày khởi hành phải nhỏ hơn ngày kết thúc!")
            elif r.start_date == r.end_date:
                if r.start_time > r.end_time:
                    raise ValidationError("Thời gian khởi hành phải nhỏ hơn thời gian kết thúc!")
            else:
                pass

    @api.constrains('amount_people')
    def validate_amount_people(self):
        for r in self:
            if r.amount_people <= 0:
                raise ValidationError("Số lượng người phải lớn hơn 0!")

    def action_cancel(self):
        for r in self:
            if (r.approve_people and r.approve_people.user_id.id == self.env.user.id) or self.env.user.id == 2:
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

    def action_edit_exist_car(self):
        for r in self:
            if (r.competency_employee and r.competency_employee.user_id.id == self.env.user.id) or self.env.user.id == 2:
                return {
                    'name': 'Nhập thông tin xe',
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.exist.car',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_parent_id': r.id,
                        'default_driver': r.driver.id,
                        'default_driver_phone': r.driver_phone,
                        'default_license_plate': r.license_plate,
                    },
                }
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def copy(self, default=None):
        current_date = datetime.now().date()
        default = dict(default or {})
        default.update({
            'status': 'draft',
            'status_exist_car': 'approved',
            'status_issuing_card': 'approved',
            'driver': None,
            'driver_phone': '',
            'license_plate': '',
            'receive_time': False,
            'return_people': None,
            'list_view_status': "Nháp",
            'reason': "",
            'reality_start_date': False,
            'reality_end_date': False,
            'type': 'draft',
            'start_date': current_date,
            'end_date': current_date,
            'start_time': 0,
            'end_time': 0,
        })
        return super(BookCar, self).copy(default)

