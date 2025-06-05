from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


class EmployeeAttendanceStore(models.Model):
    _name = 'employee.attendance.store'
    _description = 'Employee Attendance Stored Data'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    date = fields.Date(string='Ngày', required=True)
    weekday = fields.Selection([
        ('0', 'Thứ hai'),
        ('1', 'Thứ ba'),
        ('2', 'Thứ tư'),
        ('3', 'Thứ năm'),
        ('4', 'Thứ sáu'),
        ('5', 'Thứ bảy'),
        ('6', 'Chủ nhật')
    ], string="Thứ")
    check_in = fields.Datetime(string='Giờ vào')
    check_out = fields.Datetime(string='Giờ ra')
    duration = fields.Float("Giờ công")
    shift = fields.Many2one('config.shift', string="Ca làm việc")
    time_check_in = fields.Datetime("Thời gian phải vào")
    time_check_out = fields.Datetime("Thời gian phải ra")
    check_no_in = fields.Datetime("Check không có check_in")
    check_no_out = fields.Datetime("Check không có check_out")

    note = fields.Selection([('no_in', "Không có check in"),
                             ('no_out', "Không có check out"),
                             ('no_shift', "Không có ca làm việc")],
                            string="Ghi chú")
    work_day = fields.Float("Ngày công")
    minutes_late = fields.Float("Số phút đi muộn")
    minutes_early = fields.Float("Số phút về sớm")

    month = fields.Integer("Tháng")
    year = fields.Integer("Năm")
    over_time = fields.Float("Giờ làm thêm")
    leave = fields.Float("Nghỉ phép")
    compensatory = fields.Float("Nghỉ bù")
    public_leave = fields.Float("Nghỉ lễ")
    c2k3 = fields.Float("Ca 2 kíp 3")
    c3k4 = fields.Float("Ca 3 kíp 4")
    shift_toxic = fields.Float("Ca độc hại")
    work_hc = fields.Float("Công hành chính")
    work_sp = fields.Float("Công Sản phẩm")

    def copy_to_stored_model(self):
        self.with_delay().copy_data_employee_attendance()
        # today = date.today()
        # first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        #
        # # Tìm tất cả các bản ghi cần xử lý
        # list_attendances = self.env['employee.attendance'].sudo().search([
        #     ('date', '>=', first_day_last_month),
        #     ('date', '<=', today)
        # ])
        #
        # # Xác định kích thước batch (ví dụ: 500 bản ghi mỗi lần)
        # batch_size = 500
        # total_records = len(list_attendances)
        #
        # for start in range(0, total_records, batch_size):
        #     # Chia thành từng batch nhỏ
        #     batch_records = list_attendances[start:start + batch_size]
        #
        #     for record in batch_records:
        #         existing_record = self.sudo().search([
        #             ('employee_id', '=', record.employee_id.id),
        #             ('date', '=', record.date)
        #         ], limit=1)
        #
        #         # Chuẩn bị dữ liệu
        #         vals = {
        #             'department_id': record.department_id.id,
        #             'weekday': record.weekday,
        #             'check_in': record.check_in,
        #             'check_out': record.check_out,
        #             'duration': record.duration,
        #             'shift': record.shift.id if record.shift else False,
        #             'time_check_in': record.time_check_in,
        #             'time_check_out': record.time_check_out,
        #             'check_no_in': record.check_no_in,
        #             'check_no_out': record.check_no_out,
        #             'note': record.note,
        #             'work_day': record.work_day,
        #             'minutes_late': record.minutes_late,
        #             'minutes_early': record.minutes_early,
        #             'month': record.month,
        #             'year': record.year,
        #             'over_time': record.over_time,
        #             'leave': record.leave,
        #             'compensatory': record.compensatory,
        #             'public_leave': record.public_leave,
        #             'c2k3': record.c2k3,
        #             'c3k4': record.c3k4,
        #         }
        #
        #         if existing_record:
        #             # Cập nhật từng trường để đảm bảo lưu dữ liệu
        #             for field, value in vals.items():
        #                 existing_record.sudo().write({field: value})
        #         else:
        #             # Tạo mới nếu không tồn tại
        #             vals.update({
        #                 'employee_id': record.employee_id.id,
        #                 'date': record.date,
        #             })
        #             self.sudo().create(vals)

    def copy_data_employee_attendance(self):
        today = date.today()
        first_day_last_month = (today.replace(day=1) - timedelta(days=1)).replace(day=1)

        # Tìm tất cả các bản ghi cần xử lý
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
                'shift_toxic': record.shift_toxic,
            }

            if existing_record:
                existing_record.sudo().write(vals)
            else:
                # Tạo mới nếu không tồn tại
                vals.update({
                    'employee_id': record.employee_id.id,
                    'date': record.date,
                })
                self.sudo().create(vals)
