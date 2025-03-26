from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date


class RegisterOvertimeUpdate(models.Model):
    _name = 'register.overtime.update'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _default_department(self):
        # Lấy phòng ban từ user đang đăng nhập
        user = self.env.user
        if user.employee_id and user.employee_id.department_id:
            return user.employee_id.department_id.id
        return False

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True, default=lambda self: self._default_department())
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True)
    employee_ids = fields.Many2many('hr.employee', 'ir_employee_overtime_rel',
                                    'employee_overtime_rel', 'overtime_rel',
                                    string='Tên nhân viên', tracking=True)
    date = fields.One2many('overtime.rel', 'overtime_id', string="Ngày", required=True)
    type = fields.Selection([
        ('one', 'Tạo cho tôi'),
        ('many', 'Tạo hộ')
    ], string="Loại đăng ký", default='one', required=True)
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    status_lv2 = fields.Selection([
        ('draft', 'Nháp'),
        ('waiting', 'Chờ duyệt'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)

    type_overtime = fields.Boolean("Kiểm tra loại đơn", default=False, compute="get_type_overtime")

    check_qltt = fields.Boolean("Check quản lý trực tiếp", default=False, compute="get_check_qltt")
    check_manager = fields.Boolean("Check giám đốc", default=False, compute="get_check_manager")
    check_user = fields.Boolean("Check nhân viên", default=False, compute="get_user")
    company_id = fields.Many2one('res.company', string="Công ty", compute="get_company_over")

    employee_security = fields.Many2one('hr.employee', compute='get_employee_security')
    all_times = fields.Text(string="Thời gian", compute="_compute_all_times", store=True)
    record_url = fields.Char(string="Record URL", compute="_compute_record_url")

    @api.depends('employee_id', 'employee_ids')
    def _compute_record_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        menu_id = self.env.ref('sonha_word_slip.menu_register_overtime_update').id
        action_id = self.env.ref('sonha_word_slip.action_register_overtime_update').id

        for record in self:
            record.record_url = (
                f"{base_url}/web#id={record.id}"
                f"&model=form.word.slip"
                f"&view_type=form"
                f"&menu_id={menu_id}"
                f"&action={action_id}"
            )

    @api.depends('date')
    def _compute_all_times(self):
        for record in self:
            times = [f"{child.date.strftime('%d/%m/%Y')} {child.start_time}h → {child.end_time}h" for child in
                     record.date if child.date and child.start_time and child.end_time]
            record.all_times = "\n".join(times) if times else "Không có dữ liệu"

    @api.constrains('employee_id', 'employee_ids', 'date')
    def _check_overtime_conflict(self):
        for record in self:
            # Lấy danh sách nhân viên của đơn đăng ký
            employee_list = record.employee_ids.ids
            if record.employee_id:
                employee_list.append(record.employee_id.id)

            # Duyệt từng dòng chi tiết làm thêm
            for overtime in record.date:
                # Lọc các bản ghi overtime khác trong cùng ngày
                conflicts = self.env["overtime.rel"].search([
                    ("date", "=", overtime.date),  # Cùng ngày
                    ("overtime_id", "!=", record.id),
                    '|',
                    ("overtime_id.employee_id", "in", employee_list),
                    ("overtime_id.employee_ids", "in", employee_list)# Nhân viên trùng
                ])

                for conflict in conflicts:
                    if not (overtime.end_time <= conflict.start_time or overtime.start_time >= conflict.end_time):
                        raise ValidationError(f"Nhân viên đã có lịch làm thêm trùng giờ vào ngày {overtime.date}!")

    @api.depends('employee_id', 'employee_ids')
    def get_employee_security(self):
        for r in self:
            if r.employee_id:
                r.employee_security = r.employee_id.parent_id.id
            elif r.employee_ids:
                r.employee_security = r.employee_ids[:1].parent_id.id
            else:
                r.employee_security = None

    @api.depends('employee_id', 'employee_ids')
    def get_company_over(self):
        for r in self:
            if r.type == 'one':
                r.company_id = r.employee_id.company_id.id
            else:
                r.company_id = r.employee_ids[:1].company_id.id

    @api.onchange('status_lv2')
    def get_check_manager(self):
        for r in self:
            if self.env.user.has_group('sonha_employee.group_manager_employee') and r.status_lv2 == 'confirm':
                r.check_manager = True
            else:
                r.check_manager = False

    @api.onchange('employee_id', 'employee_ids', 'status_lv2')
    def get_check_qltt(self):
        for r in self:
            if r.type == 'one':
                if r.employee_id.parent_id.user_id.id == self.env.user.id and r.status_lv2 == 'waiting':
                    r.check_qltt = True
                else:
                    r.check_qltt = False
            else:
                if r.employee_ids[:1].parent_id.user_id.id == self.env.user.id and r.status_lv2 == 'waiting':
                    r.check_qltt = True
                else:
                    r.check_qltt = False

    @api.onchange('employee_id', 'employee_ids')
    def get_type_overtime(self):
        for r in self:
            if r.type == 'one':
                if r.employee_id.company_id.overtime:
                    r.type_overtime = True
                else:
                    r.type_overtime = False
            else:
                if r.employee_ids[:1].company_id.overtime:
                    r.type_overtime = True
                else:
                    r.type_overtime = False

    def create(self, vals):
        res = super(RegisterOvertimeUpdate, self).create(vals)
        if not res.type_overtime:
            template = self.env.ref('sonha_word_slip.template_sent_mail_manager_ot')
            template.send_mail(res.id, force_send=True)
        return res

    @api.onchange('employee_id', 'employee_ids', 'status_lv2', 'type_overtime')
    def get_user(self):
        for r in self:
            if r.type == 'one':
                if (r.employee_id.user_id.id == self.env.user.id or r.create_uid.id == self.env.user.id) and r.status_lv2 == 'draft':
                    r.check_user = True
                else:
                    r.check_user = False
            else:
                if (r.employee_id[:1].user_id.id == self.env.user.id or r.create_uid.id == self.env.user.id) and r.status_lv2 == 'draft':
                    r.check_user = True
                else:
                    r.check_user = False

    def action_sent(self):
        for r in self:
            if r.check_user:
                r.status_lv2 = 'waiting'
                template = self.env.ref('sonha_word_slip.template_sent_mail_manager_ot')
                template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def action_confirm_status(self):
        for r in self:
            if r.check_qltt:
                r.status_lv2 = 'confirm'
                template = self.env.ref('sonha_word_slip.template_sent_mail_gd_ot')
                template.send_mail(r.id, force_send=True)
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def action_done(self):
        for r in self:
            if r.check_manager:
                r.status_lv2 = 'done'
                r.status = 'done'
                over_time = 0
                for ot in r.date:
                    time_ot = ot.end_time - ot.start_time
                    over_time += time_ot
                list_employee = r.employee_ids or [r.employee_id]
                for employee in list_employee:
                    employee.total_compensatory += over_time
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def action_back_status(self):
        for r in self:
            over_time = 0
            for ot in r.date:
                time_ot = ot.end_time - ot.start_time
                over_time += time_ot
            list_employee = r.employee_ids or [r.employee_id]
            if list_employee[0].parent_id.id == self.env.user.employee_id.id or self.env.user.has_group('sonha_employee.group_manager_employee'):
                r.status = 'draft'
                r.status_lv2 = 'draft'
                for employee in list_employee:
                    employee.total_compensatory -= over_time
            else:
                raise ValidationError('Bạn không có quyền hoàn duyệt đơn này')

    def action_confirm(self):
        for r in self:
            over_time = 0
            for ot in r.date:
                time_ot = ot.end_time - ot.start_time
                over_time += time_ot
            if r.type == 'one':
                if r.employee_id.parent_id.user_id.id == self.env.user.id:
                    r.status = 'done'
                    r.employee_id.total_compensatory += over_time
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")
            else:
                employee_id = r.employee_ids[:1]
                if employee_id.parent_id.user_id.id == self.env.user.id:
                    r.status = 'done'
                    for employee in r.employee_ids:
                        employee.total_compensatory += over_time
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def action_back_confirm(self):
        for r in self:
            r.status = 'draft'

    def unlink(self):
        for r in self:
            if r.status != 'draft':
                raise ValidationError("chỉ được xóa bản ghi ở trạng thái nháp")
        return super(RegisterOvertimeUpdate, self).unlink()


