from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date
import requests
import json


class FormWordSlip(models.Model):
    _name = 'form.word.slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _default_department(self):
        # Lấy phòng ban từ user đang đăng nhập
        user = self.env.user
        if user.employee_id and user.employee_id.department_id:
            return user.employee_id.department_id.id
        return False

    department = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True, default=lambda self: self._default_department())
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True)
    type = fields.Many2one('config.word.slip', "Loại đơn", tracking=True, required=True)
    word_slip_id = fields.One2many('word.slip', 'word_slip', string="Ngày", tracking=True)
    description = fields.Text("Lý do", tracking=True)
    status = fields.Selection([
        ('sent', 'Nháp'),
        ('draft', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='sent')
    state_ids = fields.Many2many('approval.state', 'form_word_slip_rel', 'form_word_slip', 'states_id', string="Trạng thái")
    day_duration = fields.Float("Khoảng cách ngày")
    employee_confirm = fields.Many2one('hr.employee', string="Người xác nhận")
    employee_approval = fields.Many2one('hr.employee', string="Người duyệt")
    status_lv2 = fields.Selection([
        ('sent', 'Nháp'),
        ('draft', 'Chờ duyệt'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='sent', tracking=True)
    status_lv1 = fields.Selection([
        ('sent', 'Nháp'),
        ('draft', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='sent', tracking=True)
    check_level = fields.Boolean("Check trạng thái theo cấp độ", default=False)
    button_confirm = fields.Boolean("Check button xác nhận", compute="get_button_confirm")
    button_done = fields.Boolean("Check button duyệt", compute="get_button_done")
    complete_approval_lv = fields.Boolean("Hoàn duyệt", compute="get_complete_approval")
    code = fields.Char("Mã đơn", compute="get_code_slip", required=False, readonly=True)
    check_sent = fields.Boolean("Check gửi duyệt", default=False, compute="_get_button_sent")
    record_url = fields.Char(string="Record URL", compute="_compute_record_url")
    check_invisible_type = fields.Boolean("Check ẩn hiện", default=False)
    regis_type = fields.Selection([
        ('one', 'Tạo cho tôi'),
        ('many', 'Tạo hộ'),
    ], string='Loại đăng ký', default='one', tracking=True, required=True)

    employee_ids = fields.Many2many('hr.employee', 'ir_employee_slip_rel',
                                    'employee_slip_rel', 'slip_rel',
                                    string='Tên nhân viên', tracking=True)

    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)
    check_cancel = fields.Boolean('Hủy', compute="get_action_cancel", default=False)
    duration = fields.Float("Số ngày nghỉ phép", compute="get_duration_leave")
    month = fields.Integer("Tháng", compute="get_month_leave", store=True)
    all_dates = fields.Text(string="Khoảng ngày", compute="_compute_all_dates", store=True)

    @api.onchange('regis_type')
    def _onchange_register_type(self):
        if self.regis_type == 'one':
            self.employee_id = self.env.user.employee_id.id
            self.employee_ids = [(5, 0, 0)]
        elif self.regis_type == 'many':
            self.employee_id = False

    @api.depends('word_slip_id')
    def _compute_all_dates(self):
        for record in self:
            dates = [f"{child.from_date.strftime('%d/%m/%Y')} → {child.to_date.strftime('%d/%m/%Y')}" for child in
                     record.word_slip_id if child.from_date and child.to_date]
            record.all_dates = ", ".join(dates) if dates else "Không có"

    @api.depends('word_slip_id')
    def get_month_leave(self):
        for r in self:
            leave = self.env['word.slip'].sudo().search([('word_slip', '=', r.id)], limit=1)
            if leave and leave.from_date:
                r.month = leave.from_date.month
            else:
                r.month = None

    def get_duration_leave(self):
        for r in self:
            leave = self.env['word.slip'].sudo().search([('word_slip', '=', r.id)])
            if leave:
                r.duration = sum(leave.mapped('duration'))
            else:
                r.duration = 0

    @api.constrains('employee_id', 'employee_ids', 'word_slip_id', 'type')
    def check_validate_leave(self):
        for r in self:
            if r.type.key == "NP":
                list_employee = r.employee_ids or [r.employee_id]
                for employee_id in list_employee:
                    if r.duration > employee_id.old_leave_balance + employee_id.new_leave_balance:
                        raise ValidationError(f"Nhân viên {employee_id.name} không còn phép!")

    @api.depends('status', 'employee_confirm', 'employee_approval')
    def get_action_cancel(self):
        for r in self:
            if r.status == 'draft' and (self.env.user.employee_id.id == r.employee_approval.id or self.env.user.employee_id.id == r.employee_confirm.id):
                r.check_cancel = True
            else:
                r.check_cancel = False

    def send_fcm_notification(self, title, content, token, user_id, type, employee_id, application_id, data_text, screen="/notification", badge=1):
        url = "https://apibaohanh.sonha.com.vn/api/thongbaohrm/send-fcm"

        payload = {
            "title": title,
            "content": content,
            "badge": badge,
            "token": token,
            "application_id": application_id,
            "user_id": user_id,
            "screen": screen,
        }

        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
            response.raise_for_status()
            res_json = json.loads(response.text)
            message_id = res_json.get("messageId")
            if response.status_code == 200:
               self.env['log.notifi'].sudo().create({
                   'badge': badge,
                   'token': token,
                   'title': title,
                   'type': type,
                   'taget_screen': screen,
                   'message_id': message_id,
                   'id_application': str(application_id),
                   'userid': str(user_id),
                   'employeeid': str(employee_id) or "",
                   'body': content,
                   'datetime': str(datetime.now()),
                   'data': data_text
               })
        except Exception as e:
            return {"error": str(e)}

    def action_noti(self, record):
        user_id = self.env['res.users'].sudo().search([('id', '=', record.create_uid.id)])
        data_text = str(record.id) + "#" + str(user_id.id) + "#" + str(user_id.employee_id.id) + "#" + str(record.code) + "#2#" + str(user_id.name)
        self.send_fcm_notification(
            title="Sơn Hà HRM",
            content="Đơn từ " + str(record.code) + " của bạn bị từ chối!",
            token=user_id.token,
            user_id=user_id.id,
            type=2,
            employee_id=user_id.employee_id.id,
            application_id=str(record.id),
            data_text=data_text
        )

    def action_cancel(self):
        for r in self:
            r.status = 'cancel'
            r.status_lv1 = 'cancel'
            r.status_lv2 = 'cancel'
            self.action_noti(r)

    @api.onchange('type')
    def get_check_invisible_type(self):
        for r in self:
            if r.type.date_and_time == 'date':
                r.check_invisible_type = False
            else:
                r.check_invisible_type = True

    def unlink(self):
        for r in self:
            if r.status != 'sent':
                raise ValidationError("Chỉ được xóa khi trạng thái là nháp!")
            self.env['word.slip'].sudo().search([('word_slip.id', '=', r.id)]).unlink()
        return super(FormWordSlip, self).unlink()

    @api.depends('employee_id')
    def _compute_record_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        menu_id = self.env.ref('sonha_word_slip.menu_form_word_slip').id
        action_id = self.env.ref('sonha_word_slip.action_form_word_slip').id

        for record in self:
            record.record_url = (
                f"{base_url}/web#id={record.id}"
                f"&model=form.word.slip"
                f"&view_type=form"
                f"&menu_id={menu_id}"
                f"&action={action_id}"
            )

    @api.depends('employee_id', 'status')
    def _get_button_sent(self):
        for r in self:
            if (r.employee_id.user_id.id == self.env.user.id or r.create_uid.id == self.env.user.id) and r.status == 'sent':
                r.check_sent = True
            else:
                r.check_sent = False

    def multi_approval(self):
        for r in self:
            if self.env.user.id == r.employee_confirm.user_id.id or self.env.user.id == r.employee_approval.user_id.id:
                pass
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

            over_time = 0
            for ot in r.word_slip_id:
                if ot.start_time != ot.end_time:
                    over_time += 8
                elif ot.start_time == ot.end_time:
                    over_time += 4
            if r.status != 'draft':
                raise ValidationError("Chỉ duyệt được những bản ghi ở trạng thái chờ duyệt!")

            if r.type.key == "NB":
                employees = r.employee_ids or [r.employee_id]
                for employee in employees:
                    employee.total_compensatory -= over_time
            r.status = 'done'
            r.status_lv1 = 'done'
            r.status_lv2 = 'done'

    def action_sent(self):
        for r in self:
            def deduct_leave(employee, duration):
                """Trừ phép nhân viên và trả về True nếu thành công, False nếu không đủ phép."""
                if duration > employee.old_leave_balance + employee.new_leave_balance:
                    raise ValidationError(f"Nhân viên {employee.name} không còn phép nữa!")

                if employee.old_leave_balance >= duration:
                    employee.old_leave_balance -= duration
                else:
                    duration -= employee.old_leave_balance
                    employee.old_leave_balance = 0
                    employee.new_leave_balance -= duration
                return True
            if not r.word_slip_id:
                raise ValidationError("Bạn không có dữ liệu ngày!")
            else:
                if r.type.key == "NP":
                    employees = r.employee_ids or [r.employee_id]
                    for employee in employees:
                        deduct_leave(employee, r.duration)
                r.status = 'draft'
                r.status_lv1 = 'draft'
                r.status_lv2 = 'draft'
                if r.check_level != True:
                    template = self.env.ref('sonha_word_slip.template_sent_mail_manager_slip')
                else:
                    template = self.env.ref('sonha_word_slip.template_sent_mail_manager_slip_lv2')
                template.send_mail(r.id, force_send=True)
            self.action_noti_manager(r)

    def action_noti_manager(self, record):
        data_text = str(record.id) + "#" + str(record.employee_approval.user_id.id) + "#" + str(record.employee_approval.id) + "#" + str(
            record.code) + "#1#" + str(record.employee_approval.user_id.name)
        self.send_fcm_notification(
            title="Sơn Hà HRM",
            content="Đơn từ " + str(record.code) + " cần bạn duyệt!",
            token=record.employee_approval.user_id.token,
            user_id=record.employee_approval.user_id.id,
            type=1,
            employee_id=record.employee_approval.id,
            application_id=str(record.id),
            data_text=data_text
        )

    @api.depends('employee_id', 'type')
    def get_code_slip(self):
        for r in self:
            if r.type and r.employee_id:
                short_code = ''.join(word[0].upper() for word in r.type.name.split())
                r.code = r.employee_id.company_id.company_code + "-" + short_code + "-" + str(r.id)
            elif r.type and r.employee_ids:
                short_code = ''.join(word[0].upper() for word in r.type.name.split())
                r.code = r.employee_ids[:1].company_id.company_code + "-" + short_code + "-" + str(r.id)
            else:
                r.code = ""

    @api.depends('employee_confirm', 'employee_approval', 'status')
    def get_complete_approval(self):
        for r in self:
            r.complete_approval_lv = False
            if (r.employee_confirm.user_id.id == self.env.user.id or r.employee_approval.user_id.id == self.env.user.id) and r.status != 'sent':
                r.complete_approval_lv = True

    def complete_approval(self):
        for r in self:
            over_time = 0
            for ot in r.word_slip_id:
                if ot.start_time != ot.end_time:
                    over_time += 8
                elif ot.start_time == ot.end_time:
                    over_time += 4
            if r.check_level != True:
                r.status_lv1 = 'sent'
            else:
                r.status_lv2 = 'sent'
            if r.status != 'sent' and r.type.key == 'NP':
                employees = r.employee_ids or [r.employee_id]
                for emp in employees:
                    emp.new_leave_balance += r.duration
            elif r.status == 'done' and r.type.key == 'NB':
                employees = r.employee_ids or [r.employee_id]
                for employee in employees:
                    employee.total_compensatory += over_time
            else:
                pass
            r.status = 'sent'

    @api.depends('employee_confirm')
    def get_button_confirm(self):
        for r in self:
            if r.employee_confirm and r.employee_confirm.user_id.id == self.env.user.id and r.status_lv2 == 'draft':
                r.button_confirm = True
            else:
                r.button_confirm = False

    @api.depends('employee_approval', 'check_level')
    def get_button_done(self):
        for record in self:
            record.button_done = False
            if record.employee_approval and record.employee_approval.user_id.id == self.env.user.id:
                if record.check_level and record.status_lv2 == 'confirm':
                    record.button_done = True
                elif not record.check_level and record.status_lv1 == 'draft':
                    record.button_done = True

    def action_confirm(self):
        for r in self:
            if r.employee_confirm.user_id.id == self.env.user.id:
                r.status_lv2 = 'confirm'
                r.button_confirm = False
                template = self.env.ref('sonha_word_slip.template_sent_mail_manager_slip')
                template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def action_approval(self):
        for r in self:
            if r.employee_approval.user_id.id != self.env.user.id:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

            # Xác định cấp duyệt
            status_level = "status_lv2" if r.check_level else "status_lv1"
            over_time = 0
            for ot in r.word_slip_id:
                if ot.start_time != ot.end_time:
                    over_time += 8
                elif ot.start_time == ot.end_time:
                    over_time += 4

            if r.type.key == "NB":
                employees = r.employee_ids or [r.employee_id]
                for employee in employees:
                    employee.total_compensatory -= over_time

            setattr(r, status_level, 'done')
            r.status = 'done'
            r.button_done = False
            self.noti_user_done(r)

    def noti_user_done(self, record):
        user_id = self.env['res.users'].sudo().search([('id', '=', record.create_uid.id)])
        data_text = str(record.id) + "#" + str(user_id.id) + "#" + str(user_id.employee_id.id) + "#" + str(
            record.code) + "#2#" + str(user_id.name)
        self.send_fcm_notification(
            title="Sơn Hà HRM",
            content="Đơn từ " + str(record.code) + " của bạn đã được phê duyệt!",
            token=user_id.token,
            user_id=user_id.id,
            type=2,
            employee_id=user_id.employee_id.id,
            application_id=str(record.id),
            data_text=data_text
        )

    # hàm check validate
    def validate_record_overlap(self, record, word_slips, form_type):
        if form_type == 'date':
            # so sánh loại đơn tính theo ngày
            if not (record.start_time and record.end_time):
                raise ValidationError("Bạn chưa hoàn thành việc chọn ca.")

            if record.start_time == 'second_half' and record.end_time == 'first_half':
                raise ValidationError("Ca bắt đầu không thể đặt sau ca kết thúc.")

            for r in word_slips:
                #nếu trùng ngày mà 1 trong 2 đơn nghỉ cả ngày thì thông báo lỗi
                if r.start_time != r.end_time or record.start_time != record.end_time:
                    raise ValidationError("Khoảng thời gian bạn chọn bị trùng với khoảng thời gian trong đơn khác.")
                # nếu không nghỉ cả ngày thì so sánh ca
                elif r.start_time == record.start_time:
                    raise ValidationError("Khoảng thời gian bạn chọn bị trùng với khoảng thời gian trong đơn khác.")
        else:  # form_type == 'time'
            # so sánh loại đơn tính theo giờ
            if not (0 <= record.time_to <= 24.0 and 0 <= record.time_from <= 24.0):
                raise ValidationError("Hãy nhập thời gian trong khoảng 0-24h")

            if record.time_to > record.time_from:
                raise ValidationError("Thời gian bắt đầu phải đặt trước thời gian kết thúc.")

            # lọc các bản ghi tìm được theo thời gian bắt đầu và thời gian kết thúc
            overlapping = word_slips.filtered(
                lambda r: not (r.time_to >= record.time_from or r.time_from <= record.time_to)
            )
            if overlapping:
                raise ValidationError("Khoảng thời gian bạn chọn bị trùng với khoảng thời gian trong đơn khác.")

    # hàm lấy dữ liệu và gọi hàm check validate
    def process_word_slip_validation(self, rec):
        # lấy type của form
        form_type = rec.type.date_and_time
        for record in rec.word_slip_id:
            day = self.env['res.company'].sudo().search([('id', '=', record.employee_id.company_id.id)], limit=1)
            if day.slip != 0:
                now = date.today()
                date_valid = now - timedelta(days=day.slip)
                if record.from_date < date_valid or record.to_date < date_valid:
                    raise ValidationError("Bạn không thể đăng ký đơn từ cho ngày quá khứ")
            if not (record.from_date and record.to_date):
                raise ValidationError("Bạn chưa hoàn thành việc chọn ngày bắt đầu và ngày kết thúc")
            if record.from_date > record.to_date:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")

            # tìm kiếm các bản ghi theo các điều kiện
            word_slips = self.env['word.slip'].sudo().search([
                ('type.date_and_time', '=', form_type),
                ('id', '!=', record.id),
                ('from_date', '<=', record.to_date),
                ('to_date', '>=', record.from_date),
                ('word_slip.status', '!=', 'cancel'),
            ])
            word_slips = word_slips.filtered(
                lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == rec.employee_id.id) or (
                        x.word_slip.employee_ids and rec.employee_id.id in x.word_slip.employee_ids.ids))
            # gọi hàm check validate
            self.validate_record_overlap(record, word_slips, form_type)

    def create(self, vals):
        rec = super(FormWordSlip, self).create(vals)

        self.env['word.slip'].sudo().check_employee_days_limit(rec.word_slip_id)

        # check validate khi tạo bản ghi mới
        self.process_word_slip_validation(rec)

        # Tính số ngày và thiết lập `day_duration`
        rec.day_duration = self.get_duration_day(rec)
        if rec.employee_id:
            employee_id = rec.employee_id
        elif rec.employee_ids:
            employee_id = rec.employee_ids[:1]

        if employee_id.parent_id.id == employee_id.employee_approval.id:
            rec.day_duration = 1

        department_spec = self.env['hr.department'].sudo().search([('name', '=', "SHI-Bộ phận xe VPTĐ"),
                                                                   ('id', '=', rec.department.id)])
        if department_spec:
            rec.check_level = True
            if employee_id.employee_approval and employee_id.parent_id:
                rec.employee_confirm = employee_id.parent_id.id
                rec.employee_approval = employee_id.employee_approval.id
            elif not employee_id.employee_approval and employee_id.parent_id:
                rec.employee_confirm = employee_id.parent_id.id
                rec.employee_approval = employee_id.parent_id.parent_id.id if employee_id.parent_id.parent_id else employee_id.department_id.parent_id.manager_id.id
            elif employee_id.employee_approval and not employee_id.parent_id:
                rec.employee_confirm = employee_id.employee_approval.id
                rec.employee_approval = employee_id.employee_approval.parent_id.id if employee_id.employee_approval.parent_id else None
                
        if (not department_spec and rec.day_duration <= 3) or rec.type.key != "NP":
            condition = '<=3'
            rec.check_level = False
        else:
            condition = '>3'
            rec.check_level = True
        status = self.env['approval.workflow.step'].sudo().search([
            ('workflow_id.department_id', '=', rec.department.id),
            ('condition', '=', condition)
        ])

        # Xử lý logic dựa trên cấp phê duyệt
        if status:
            if status.level <= 1:
                rec.employee_confirm = None
                rec.employee_approval = employee_id.employee_approval.id if employee_id.employee_approval else employee_id.parent_id.id
            else:
                rec.check_level = True
                if employee_id.employee_approval and employee_id.parent_id:
                    rec.employee_confirm = employee_id.parent_id.id
                    rec.employee_approval = employee_id.employee_approval.id
                elif not employee_id.employee_approval and employee_id.parent_id:
                    rec.employee_confirm = employee_id.parent_id.id
                    rec.employee_approval = employee_id.parent_id.parent_id.id if employee_id.parent_id.parent_id else employee_id.department_id.parent_id.manager_id.id
                elif employee_id.employee_approval and not employee_id.parent_id:
                    rec.employee_confirm = employee_id.employee_approval.id
                    rec.employee_approval = employee_id.employee_approval.parent_id.id if employee_id.employee_approval.parent_id else None
        else:
            # Trường hợp không có bước phê duyệt
            rec.employee_approval = employee_id.employee_approval.id if employee_id.employee_approval else employee_id.parent_id.id
        return rec

    def get_duration_day(self, rec):
        word_slip = self.env['word.slip'].sudo().search([('word_slip', '=', rec.id)], limit=1)
        if word_slip and word_slip.from_date and word_slip.to_date:
            start_date = fields.Date.from_string(word_slip.from_date)
            end_date = fields.Date.from_string(word_slip.to_date)
            day_duration = (end_date - start_date).days + 1
        else:
            day_duration = 0
        return day_duration

    @api.constrains('employee_id')
    def check_word_slip_id(self):
        for r in self:
            total_duration = 0
            list_employees = r.employee_id or r.employee_ids
            if r.word_slip_id and r.type.name.lower() == "nghỉ bù":
                for slip in r.word_slip_id:
                    total_duration += slip.duration * 8
                for emp in list_employees:
                    if emp.total_compensatory < total_duration:
                        raise ValidationError("Nhân viên " + emp.name + " không còn thời gian nghỉ bù")

    @api.constrains('word_slip_id')
    def validate_word_slip_id(self):
        for r in self:
            if not r.word_slip_id:
                raise ValidationError("Không được để trống ngày!")
            else:
                for slip in r.word_slip_id:
                    if not slip.from_date:
                        raise ValidationError("Không được để trống trường từ ngày!")
                    if not slip.to_date:
                        raise ValidationError("Không được để trống trường đến ngày!")
                    if not slip.reason:
                        raise ValidationError("Không được để trống trường lý do!")
                    if slip.word_slip.type.date_and_time == 'date':
                        if not slip.start_time or not slip.end_time:
                            raise ValidationError("Không được để trống ca bắt đầu và ca kết thúc!")

    @api.constrains('type', 'word_slip_id')
    def check_type(self):
        for r in self:
            if r.word_slip_id and r.type.max_time != 0:
                for slip in r.word_slip_id:
                    total_hours = slip.time_from - slip.time_to
                    if total_hours > r.type.max_time:
                        raise ValidationError("Loại đơn " + str(r.type.name) + " chỉ được phép tạo tối đa " + str(r.type.max_time) + " giờ")

    def write(self, vals):
        res = super(FormWordSlip, self).write(vals)
        if 'word_slip_id' in vals:
            for record in self:
                # check validate
                self.process_word_slip_validation(record)
                self.env['word.slip'].sudo().check_employee_days_limit(record.word_slip_id)
        return res