from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date


class RegisterOvertime(models.Model):
    _name = 'register.overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True)
    start_date = fields.Date("Từ ngày", tracking=True, required=True)
    end_date = fields.Date("Đến ngày", tracking=True, required=True)
    start_time = fields.Float("Thời gian bắt đầu", tracking=True, required=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True, required=True)
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    def action_confirm(self):
        for r in self:
            if r.employee_id.parent_id.user_id.id == self.env.user.id:
                r.status = 'done'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này")

    def multi_approval(self):
        for r in self:
            r.status = 'done'

    def unlink(self):
        for r in self:
            if r.status != 'draft':
                raise ValidationError("chỉ được xóa bản ghi ở trạng thái nháp")
        return super(RegisterOvertime, self).unlink()

    def action_back_confirm(self):
        for r in self:
            r.status = 'draft'

    def create(self, vals):
        rec = super(RegisterOvertime, self).create(vals)
        self._check_validity(rec)
        return rec

    def write(self, vals):
        res = super(RegisterOvertime, self).write(vals)
        if 'start_date' in vals or 'end_date' in vals:
            for record in self:
                self._check_validity(record)
        return res

    def _check_validity(self, rec):
        day = self.env['res.company'].sudo().search([('id', '=', rec.employee_id.company_id.id)], limit=1)
        if rec.employee_id and day and day.shift != 0:
            now = date.today()
            date_valid = now - timedelta(days=day.slip)
            if rec.start_date < date_valid or rec.end_date < date_valid:
                raise ValidationError("Bạn không thể đăng ký làm thêm giờ cho ngày quá khứ")
