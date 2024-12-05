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
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft')
    state_ids = fields.Many2many('approval.state', 'form_word_slip_rel', 'form_word_slip', 'states_id', string="Trạng thái")
    day_duration = fields.Float("Khoảng cách ngày")
    employee_confirm = fields.Many2one('hr.employee', string="Người xác nhận")
    employee_approval = fields.Many2one('hr.employee', string="Người duyệt")
    status_lv2 = fields.Selection([
        ('draft', 'Chờ duyệt'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    status_lv1 = fields.Selection([
        ('draft', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    check_level = fields.Boolean("Check trạng thái theo cấp độ", default=False)
    button_confirm = fields.Boolean("Check button xác nhận", compute="get_button_confirm")
    button_done = fields.Boolean("Check button duyệt", compute="get_button_done")
    complete_approval_lv = fields.Boolean("Hoàn duyệt", compute="get_complete_approval")

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

    def create(self, vals):
        rec = super(FormWordSlip, self).create(vals)

        # Tính số ngày và thiết lập `day_duration`
        rec.day_duration = self.get_duration_day(rec)

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
            rec.employee_approval = rec.employee_id.employee_approval.id if rec.employee_id.employee_approval else rec.employee_id.parent_id.id
        return rec

    def get_duration_day(self, rec):
        word_slip = self.env['word.slip'].sudo().search([('word_slip', '=', rec.id)], limit=1)
        if word_slip:
            start_date = fields.Date.from_string(word_slip.from_date)
            end_date = fields.Date.from_string(word_slip.to_date)
            day_duration = (end_date - start_date).days + 1
        else:
            day_duration = 0
        return day_duration

