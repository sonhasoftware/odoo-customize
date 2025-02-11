from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date


class RegisterOvertime(models.Model):
    _name = 'register.overtime'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", tracking=True, required=True)
    start_date = fields.Date("Từ ngày", tracking=True)
    end_date = fields.Date("Đến ngày", tracking=True)
    date = fields.Date("Ngày", tracking=True)
    start_time = fields.Float("Thời gian bắt đầu", tracking=True, required=True)
    end_time = fields.Float("Thời gian kết thúc", tracking=True, required=True)
    status = fields.Selection([
        ('draft', 'Nháp'),
        ('done', 'Đã duyệt'),
    ], string='Trạng thái', default='draft', tracking=True)

    @api.onchange('date')
    def get_data_date(self):
        for r in self:
            if r.date:
                r.start_date = r.date
                r.end_date = r.date
            else:
                pass


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

    @api.constrains('employee_id', 'start_time', 'end_time', 'start_date', 'end_date')
    def _check_time_overlap(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError("Giờ bắt đầu phải nhỏ hơn giờ kết thúc.")

            # Tìm tất cả các bản ghi có cùng nhân viên và có thể bị trùng thời gian
            domain = [
                ('id', '!=', record.id),  # Loại trừ bản ghi hiện tại nếu đang cập nhật
                ('employee_id', '=', record.employee_id.id),  # Cùng một nhân viên
                ('start_date', '<=', record.end_date),  # Có thể giao nhau về ngày
                ('end_date', '>=', record.start_date),
            ]
            overlapping_records = self.search(domain)

            for overlap in overlapping_records:
                # Kiểm tra trùng giờ trong cùng ngày
                if not (record.end_time <= overlap.start_time or record.start_time >= overlap.end_time):
                    raise ValidationError(f"Nhân viên {record.employee_id.name} đã có lịch từ "
                                          f"{overlap.start_time}h đến {overlap.end_time}h trong ngày "
                                          f"{overlap.start_date} - {overlap.end_date}, không thể tạo mới.")
