from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class FormWordSlip(models.Model):
    _name = 'form.word.slip'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True)
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
        ('draft', 'Nháp'),
        ('confirm', 'Chờ duyệt'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    status_lv1 = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    check_level = fields.Boolean("Check trạng thái theo cấp độ", default=False)
    button_confirm = fields.Boolean("Check button xác nhận", compute="get_button_confirm")
    button_done = fields.Boolean("Check button duyệt", compute="get_button_done")

    @api.depends('employee_confirm')
    def get_button_confirm(self):
        for r in self:
            if r.employee_confirm and r.employee_confirm.user_id.id == self.env.user.id:
                r.button_confirm = True
            else:
                r.button_confirm = False

    @api.depends('employee_approval')
    def get_button_done(self):
        for r in self:
            if r.employee_approval and r.employee_approval.user_id.id == self.env.user.id:
                r.button_done = True
            else:
                r.button_done = False

    def action_confirm(self):
        for r in self:
            if r.employee_confirm.user_id.id == self.env.user.id:
                r.status_lv2 = 'confirm'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    @api.constrains('word_slip_id')
    def check_word_slip_id(self):
        if not self.word_slip_id:
            raise ValidationError(f"Đơn từ của bạn chưa chọn thời gian")
    def action_approval(self):
        for r in self:
            if r.check_level != True:
                if r.employee_approval.user_id.id == self.env.user.id:
                    r.status_lv1 = 'done'
                    r.status = 'done'
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")
            else:
                if r.employee_approval.user_id.id == self.env.user.id:
                    r.status_lv2 = 'done'
                    r.status = 'done'
                else:
                    raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def create(self, vals):
        rec = super(FormWordSlip, self).create(vals)

        # Tính số ngày và thiết lập `day_duration`
        rec.day_duration = self.get_duration_day(rec)

        # Kiểm tra người phê duyệt trực tiếp từ nhân viên
        if rec.employee_id.employee_approval:
            rec.employee_approval = rec.employee_id.employee_approval.id
        else:
            # Điều kiện tìm kiếm bước phê duyệt
            condition = '<=3' if rec.day_duration <= 3 else '>3'
            status = self.env['approval.workflow.step'].sudo().search([
                ('workflow_id.department_id', '=', rec.department.id),
                ('leave', '=', rec.type.id),
                ('condition', '=', condition)
            ])

            # Xử lý logic dựa trên cấp phê duyệt
            if status:
                if status.level <= 1:
                    rec.employee_confirm = None
                    rec.employee_approval = rec.employee_id.parent_id.id
                else:
                    rec.check_level = True
                    rec.employee_confirm = rec.employee_id.parent_id.id
                    rec.employee_approval = rec.employee_id.parent_id.parent_id.id
            else:
                # Trường hợp không có bước phê duyệt
                rec.employee_approval = rec.employee_id.parent_id.id

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

