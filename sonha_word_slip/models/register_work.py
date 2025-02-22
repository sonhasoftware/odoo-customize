from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
from odoo.exceptions import UserError, ValidationError


class RegisterWork(models.Model):
    _name = 'register.work'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _default_department(self):
        # Lấy phòng ban từ user đang đăng nhập
        user = self.env.user
        if user.employee_id and user.employee_id.department_id:
            return user.employee_id.department_id.id
        return False

    employee_id = fields.Many2many('hr.employee', 'register_work_rel',
                                   'register_work', 'register_work_id',
                                   string="Tên nhân viên", tracking=True, required=True)
    shift = fields.Many2one('config.shift', string="Ca", tracking=True, required=True)
    start_date = fields.Date("Từ ngày", tracking=True, required=True)
    end_date = fields.Date("Đến ngày", tracking=True, required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True, default=lambda self: self._default_department())
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

    #Chỉ hiển thị các nhân viên trong phòng ban đã chọn
    @api.onchange('department_id')
    def _onchange_department_id(self):
        for r in self:
            if r.department_id:
                return {
                    'domain': {
                        'employee_id': [('department_id', '=', self.department_id.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'employee_id': []
                    }
                }

    def create(self, vals):
        list_record = super(RegisterWork, self).create(vals)
        for record in list_record:
            self.sudo().create_distribute_shift(record)
        return list_record

    def create_distribute_shift(self, record):
        for emp in record.employee_id:
            temp_date = record.start_date
            while temp_date <= record.end_date:
                emp_id = emp.id
                vals = {
                    'employee_id': emp_id or '',
                    'date': temp_date or '',
                    'shift': record.shift.id or '',
                }
                self.env['distribute.shift'].sudo().create(vals)
                temp_date = temp_date + timedelta(days=1)

    @api.constrains('start_date', 'end_date')
    def _check_validity(self):
        for r in self:
            day = self.env['res.company'].sudo().search([('id', '=', r.employee_id.company_id.id)], limit=1)
            if r.employee_id and day and day.shift != 0:
                now = date.today()
                date_valid = now - timedelta(days=day.shift)
                if r.start_date < date_valid or r.end_date < date_valid:
                    raise ValidationError("Bạn không thể đăng ký ca cho ngày quá khứ")

    @api.constrains('start_date', 'end_date', 'start_time', 'end_time', 'employee_id')
    def _check_time_overlap(self):
        for record in self:
            if record.start_time >= record.end_time:
                raise ValidationError("Giờ bắt đầu phải nhỏ hơn giờ kết thúc.")

            if record.start_date > record.end_date:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")

            for employee in record.employee_id:
                overlapping_schedules = self.env['employee.schedule'].search([
                    ('id', '!=', record.id),  # Loại trừ chính bản ghi hiện tại
                    ('employee_id', 'in', employee.id),  # Chỉ xét lịch của nhân viên này
                    '|', '&',
                    ('start_date', '<=', record.end_date),
                    ('end_date', '>=', record.start_date),  # Trùng ngày
                    '|', '&',
                    ('start_time', '<', record.end_time),
                    ('end_time', '>', record.start_time)  # Trùng giờ
                ])

                if overlapping_schedules:
                    raise ValidationError(f"Nhân viên {employee.name} đã có lịch trùng thời gian.")


