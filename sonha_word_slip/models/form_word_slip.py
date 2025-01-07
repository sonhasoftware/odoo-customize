from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    @api.model
    def _default_employee(self):
        # Lấy phòng ban từ user đang đăng nhập
        user = self.env.user
        if user.employee_id:
            return user.employee_id.id
        return False

    department = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True, default=lambda self: self._default_department())
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True, default=lambda self: self._default_employee())
    type = fields.Many2one('config.word.slip', "Loại đơn", tracking=True, required=True)
    word_slip_id = fields.One2many('word.slip', 'word_slip', string="Ngày", tracking=True)
    description = fields.Text("Lý do", tracking=True)
    status = fields.Selection([
        ('sent', 'Nháp'),
        ('draft', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
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

    @api.onchange('type')
    def get_check_invisible_type(self):
        for r in self:
            if r.type.date_and_time == 'date':
                r.check_invisible_type = False
            else:
                r.check_invisible_type = True

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
            r.status = 'done'
            r.status_lv1 = 'done'
            r.status_lv2 = 'done'

    def action_sent(self):
        for r in self:
            r.status = 'draft'
            r.status_lv1 = 'draft'
            r.status_lv2 = 'draft'
            if r.check_level != True:
                template = self.env.ref('sonha_word_slip.template_sent_mail_manager_slip')
            else:
                template = self.env.ref('sonha_word_slip.template_sent_mail_manager_slip_lv2')
            template.send_mail(r.id, force_send=True)

    @api.depends('employee_id', 'type')
    def get_code_slip(self):
        for r in self:
            if r.type and r.employee_id:
                short_code = ''.join(word[0].upper() for word in r.type.name.split())
                r.code = "SSP-" + short_code + "-" + str(r.id)
            else:
                r.code = ""

    @api.depends('employee_confirm', 'employee_approval', 'status')
    def get_complete_approval(self):
        for r in self:
            r.complete_approval_lv = False
            if (r.employee_confirm.user_id.id == self.env.user.id or r.employee_approval.user_id.id == self.env.user.id) and r.status == 'done':
                r.complete_approval_lv = True

    def complete_approval(self):
        for r in self:
            if r.check_level != True:
                r.status_lv1 = 'draft'
            else:
                r.status_lv2 = 'draft'
            r.status = 'draft'

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
            if r.check_level != True:
                if r.employee_approval.user_id.id == self.env.user.id:
                    r.status_lv1 = 'done'
                    r.status = 'done'
                    r.button_done = False
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")
            else:
                if r.employee_approval.user_id.id == self.env.user.id:
                    r.status_lv2 = 'done'
                    r.status = 'done'
                    r.button_done = False
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")

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
            if not (record.from_date and record.to_date):
                raise ValidationError("Bạn chưa hoàn thành việc chọn ngày bắt đầu và ngày kết thúc")
            if record.from_date > record.to_date:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")

            # tìm kiếm các bản ghi theo các điều kiện
            word_slips = self.env['word.slip'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('type.date_and_time', '=', form_type),
                ('id', '!=', record.id),
                ('from_date', '<=', record.to_date),
                ('to_date', '>=', record.from_date),
            ])
            # gọi hàm check validate
            self.validate_record_overlap(record, word_slips, form_type)

    def create(self, vals):
        rec = super(FormWordSlip, self).create(vals)

        # check validate khi tạo bản ghi mới
        self.process_word_slip_validation(rec)

        # Tính số ngày và thiết lập `day_duration`
        rec.day_duration = self.get_duration_day(rec)

        if rec.employee_id.parent_id.id == rec.employee_id.employee_approval.id:
            rec.day_duration = 1

        department_spec = self.env['hr.department'].sudo().search([('name', '=', "SHI-Bộ phận xe VPTĐ"),
                                                                   ('id', '=', rec.department.id)])
        if department_spec:
            rec.check_level = True
            if rec.employee_id.employee_approval and rec.employee_id.parent_id:
                rec.employee_confirm = rec.employee_id.parent_id.id
                rec.employee_approval = rec.employee_id.employee_approval.id
            elif not rec.employee_id.employee_approval and rec.employee_id.parent_id:
                rec.employee_confirm = rec.employee_id.parent_id.id
                rec.employee_approval = rec.employee_id.parent_id.parent_id.id if rec.employee_id.parent_id.parent_id else rec.employee_id.department_id.parent_id.manager_id.id
            elif rec.employee_id.employee_approval and not rec.employee_id.parent_id:
                rec.employee_confirm = rec.employee_id.employee_approval.id
                rec.employee_approval = rec.employee_id.employee_approval.parent_id.id if rec.employee_id.employee_approval.parent_id else None
                
        if not department_spec and rec.day_duration <= 3:
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
                rec.employee_approval = rec.employee_id.employee_approval.id if rec.employee_id.employee_approval else rec.employee_id.parent_id.id
            else:
                rec.check_level = True
                if rec.employee_id.employee_approval and rec.employee_id.parent_id:
                    rec.employee_confirm = rec.employee_id.parent_id.id
                    rec.employee_approval = rec.employee_id.employee_approval.id
                elif not rec.employee_id.employee_approval and rec.employee_id.parent_id:
                    rec.employee_confirm = rec.employee_id.parent_id.id
                    rec.employee_approval = rec.employee_id.parent_id.parent_id.id if rec.employee_id.parent_id.parent_id else rec.employee_id.department_id.parent_id.manager_id.id
                elif rec.employee_id.employee_approval and not rec.employee_id.parent_id:
                    rec.employee_confirm = rec.employee_id.employee_approval.id
                    rec.employee_approval = rec.employee_id.employee_approval.parent_id.id if rec.employee_id.employee_approval.parent_id else None
        else:
            # Trường hợp không có bước phê duyệt
            rec.employee_approval = rec.employee_id.parent_id.id if rec.employee_id.parent_id else rec.employee_id.employee_approval.id
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

    @api.constrains('word_slip_id')
    def check_word_slip_id(self):
        if not self.word_slip_id:
            raise ValidationError(f"Đơn từ của bạn chưa chọn thời gian")

    @api.constrains('employee_id')
    def check_word_slip_id(self):
        for r in self:
            total_duration = 0
            if r.word_slip_id and r.type.name.lower() == "nghỉ bù":
                for slip in r.word_slip_id:
                    total_duration += slip.duration * 8
            if r.employee_id.total_compensatory < total_duration:
                raise ValidationError("Bạn không còn thời gian nghỉ bù")

    def write(self, vals):
        res = super(FormWordSlip, self).write(vals)
        if 'word_slip_id' in vals:
            for record in self:
                # check validate
                self.process_word_slip_validation(record)
        return res