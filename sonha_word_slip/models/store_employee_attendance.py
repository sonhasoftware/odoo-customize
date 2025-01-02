from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


class EmployeeAttendanceStore(models.Model):
    _name = 'employee.attendance.store'
    _description = 'Employee Attendance Stored Data'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', store=True)
    date = fields.Date(string='Ngày', required=True, store=True)
    weekday = fields.Selection([
        ('0', 'Thứ hai'),
        ('1', 'Thứ ba'),
        ('2', 'Thứ tư'),
        ('3', 'Thứ năm'),
        ('4', 'Thứ sáu'),
        ('5', 'Thứ bảy'),
        ('6', 'Chủ nhật')
    ], string="Thứ", store=True)
    check_in = fields.Datetime(string='Giờ vào', store=True)
    check_out = fields.Datetime(string='Giờ ra', store=True)
    duration = fields.Float("Giờ công", store=True)
    shift = fields.Many2one('config.shift', string="Ca làm việc", store=True)
    time_check_in = fields.Datetime("Thời gian phải vào", store=True)
    time_check_out = fields.Datetime("Thời gian phải ra", store=True)
    check_no_in = fields.Datetime("Check không có check_in", store=True)
    check_no_out = fields.Datetime("Check không có check_out", store=True)

    note = fields.Selection([('no_in', "Không có check in"),
                             ('no_out', "Không có check out")],
                            string="Ghi chú", store=True)
    work_day = fields.Float("Ngày công", store=True)
    minutes_late = fields.Float("Số phút đi muộn", store=True)
    minutes_early = fields.Float("Số phút về sớm", store=True)

    month = fields.Integer("Tháng", store=True)
    year = fields.Integer("Năm", store=True)
    over_time = fields.Float("Giờ làm thêm", store=True)
    leave = fields.Float("Nghỉ phép", store=True)
    compensatory = fields.Float("Nghỉ bù", store=True)
    public_leave = fields.Float("Nghỉ lễ", store=True)
    c2k3 = fields.Float("Ca 2 kíp 3", store=True)
    c3k4 = fields.Float("Ca 3 kíp 4", store=True)

    def copy_to_stored_model(self):
        today = date.today()
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        list_attendances = self.env['employee.attendance'].sudo().search([
            ('date', '>=', first_day_last_month),
            ('date', '<=', today)
        ])
        for record in list_attendances:
            existing_record = self.sudo().search([
                ('employee_id', '=', record.employee_id.id),
                ('date', '=', record.date)
            ], limit=1)

            # Chuẩn bị dữ liệu
            vals = {
                'department_id': record.department_id.id,
                'weekday': record.weekday,
                'check_in': record.check_in,
                'check_out': record.check_out,
                'duration': record.duration,
                'shift': record.shift.id if record.shift else False,
                'time_check_in': record.time_check_in,
                'time_check_out': record.time_check_out,
                'check_no_in': record.check_no_in,
                'check_no_out': record.check_no_out,
                'note': record.note,
                'work_day': record.work_day,
                'minutes_late': record.minutes_late,
                'minutes_early': record.minutes_early,
                'month': record.month,
                'year': record.year,
                'over_time': record.over_time,
                'leave': record.leave,
                'compensatory': record.compensatory,
                'public_leave': record.public_leave,
                'c2k3': record.c2k3,
                'c3k4': record.c3k4,
            }

            if existing_record:
                # Cập nhật từng trường để đảm bảo lưu dữ liệu
                for field, value in vals.items():
                    existing_record.sudo().write({field: value})
            else:
                # Tạo mới nếu không tồn tại
                vals.update({
                    'employee_id': record.employee_id.id,
                    'date': record.date,
                })
                self.sudo().create(vals)
