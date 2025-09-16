from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
import requests
import json


class EmployeeAttendance(models.Model):
    _name = 'employee.attendance'
    _description = 'Employee Attendance'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', compute="_get_department_id", store=True)
    date = fields.Date(string='Ngày', required=True, store=True)
    weekday = fields.Selection([
        ('0', 'Thứ hai'),
        ('1', 'Thứ ba'),
        ('2', 'Thứ tư'),
        ('3', 'Thứ năm'),
        ('4', 'Thứ sáu'),
        ('5', 'Thứ bảy'),
        ('6', 'Chủ nhật')
    ], string="Thứ", compute="_compute_weekday", store=True)
    check_in = fields.Datetime(string='Giờ vào', compute="_get_check_in_out")
    check_out = fields.Datetime(string='Giờ ra', compute="_get_check_in_out")
    duration = fields.Float("Giờ công", compute="_get_duration")
    shift = fields.Many2one('config.shift', compute="_get_shift_employee", string="Ca làm việc")
    time_check_in = fields.Datetime("Thời gian phải vào", compute="_get_time_in_out")
    time_check_out = fields.Datetime("Thời gian phải ra", compute="_get_time_in_out")
    check_no_in = fields.Datetime("Check không có check_in", compute="_check_no_in_out")
    check_no_out = fields.Datetime("Check không có check_out", compute="_check_no_in_out")

    note = fields.Selection([('no_in', "Không có check in"),
                             ('no_out', "Không có check out"),
                             ('no_shift', "Không có ca làm việc")],
                            string="Ghi chú",
                            compute="_get_attendance")
    work_day = fields.Float("Ngày công", compute="_get_work_day")
    minutes_late = fields.Float("Số phút đi muộn", compute="_get_minute_late_early")
    minutes_early = fields.Float("Số phút về sớm", compute="_get_minute_late_early")

    month = fields.Integer("Tháng", compute="_get_month_year", store=True)
    year = fields.Integer("Năm", compute="_get_month_year")
    over_time = fields.Float("Giờ làm thêm", compute="get_hours_reinforcement")
    over_time_nb = fields.Float("Làm thêm hưởng NB", compute="get_hours_reinforcement")
    leave = fields.Float("Nghỉ phép", compute="_get_time_off")
    compensatory = fields.Float("Nghỉ bù", compute="_get_time_off")
    public_leave = fields.Float("Nghỉ lễ", cumpute="_get_time_off")
    c2k3 = fields.Float("Ca 2 kíp 3", compute="get_shift")
    c3k4 = fields.Float("Ca 3 kíp 4", compute="get_shift")
    shift_toxic = fields.Float("Ca độc hại", compute="get_shift")
    work_hc = fields.Float("Công hành chính", compute="get_work_hc_sp")
    work_sp = fields.Float("Công Sản phẩm", compute="get_work_hc_sp")
    times_late = fields.Integer("Đi muộn quá 30p", compute="get_times_late")
    work_calendar = fields.Boolean("Lịch làm việc", compute="get_work_calendar")
    actual_work = fields.Float("Công thực tế theo ca", compute="_get_actual_work")
    vacation = fields.Float("Nghỉ mát", compute="_get_time_off")
    forgot_time = fields.Integer("Quên CI/CO", compute="_get_forgot_time")
    work_eat = fields.Integer("Công ăn", compute="_get_work_eat")

    @api.depends('date', 'shift')
    def get_work_calendar(self):
        for r in self:
            r.work_calendar = True
            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]
            if r.shift and r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.work_calendar = False

    @api.depends('shift')
    def get_work_hc_sp(self):
        for r in self:
            r.work_sp = 0
            r.work_hc = 0
            if r.shift and r.shift.type_shift == 'sp':
                r.work_sp = r.work_day
            else:
                r.work_hc = r.work_day

    @api.depends('shift')
    def get_shift(self):
        for r in self:
            # Reset giá trị mặc định
            r.c2k3 = 0
            r.c3k4 = 0
            r.shift_toxic = 0

            # Nếu shift tồn tại, kiểm tra các điều kiện
            if r.shift:
                r.c2k3 = 1 if r.shift.c2k3 else 0
                r.c3k4 = 1 if r.shift.c3k4 else 0
                r.shift_toxic = r.work_day if r.shift.shift_toxic else 0

    @api.depends('employee_id', 'date')
    def _get_time_off(self):
        # Lấy tất cả public leaves một lần, giảm số lần truy vấn
        all_public_leaves = self.env['resource.calendar.leaves'].sudo().search([])

        for r in self:
            # Khởi tạo giá trị mặc định
            r.leave = 0
            r.compensatory = 0
            r.public_leave = 0
            r.vacation = 0

            if not r.employee_id or not r.date:
                continue

            # Tìm tất cả các word.slip liên quan
            word_slips = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('word_slip.status', '=', 'done')
            ])

            word_slips = word_slips.filtered(lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            # Xử lý word.slip
            for slip in word_slips:
                type_name = slip.word_slip.type.name.lower()
                key = slip.word_slip.type.key.lower()
                if type_name == "nghỉ phép":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.leave = 1
                        else:
                            r.leave = 0.5
                    else:
                        r.leave = 0
                elif type_name == "nghỉ bù":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.compensatory = 1
                        else:
                            r.compensatory = 0.5
                    else:
                        r.compensatory = 0
                elif key == "tbd":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.vacation = 1
                        else:
                            r.vacation = 0.5
                    else:
                        r.vacation = 0

            # Kiểm tra public leave
            if all_public_leaves.filtered(
                    lambda leave: leave.date_from.date() <= r.date <= leave.date_to.date()):
                r.public_leave = 1

    @api.depends('employee_id', 'date', 'check_in', 'check_out', 'shift')
    def get_hours_reinforcement(self):
        for record in self:
            record.over_time_nb = 0
            total_overtime = 0
            ot = self.env['register.overtime'].sudo().search([('employee_id', '=', record.employee_id.id),
                                                              ('start_date', '<=', record.date),
                                                              ('end_date', '>=', record.date),
                                                              ('status', '=', 'done')])

            overtime = self.env['overtime.rel'].sudo().search([
                '&',
                ('date', '=', record.date),
                '|',
                ('overtime_id.status', '=', 'done'),
                ('overtime_id.status_lv2', '=', 'done'),
            ])
            overtime = overtime.filtered(lambda x: (x.overtime_id.employee_id and x.overtime_id.employee_id.id == record.employee_id.id)
                                                   or (x.overtime_id.employee_ids and record.employee_id.id in x.overtime_id.employee_ids.ids))
            if ot:
                for r in ot:
                    if r.start_date != r.end_date and r.start_time > r.end_time:
                        if r.start_date == record.date:
                            total_overtime += abs(24 - r.start_time)
                        elif r.end_date == record.date:
                            total_overtime += abs(r.end_time)
                    else:
                        total_overtime += abs(r.end_time - r.start_time)
            if overtime:
                for x in overtime:
                    if not record.shift:
                        continue

                    # Giờ ca làm (float giờ)
                    if not record.shift.shift_ot:
                        shift_start = (record.shift.start + relativedelta(hours=7)).hour + \
                                      (record.shift.start + relativedelta(hours=7)).minute / 60
                        shift_end = (record.shift.end_shift + relativedelta(hours=7)).hour + \
                                    (record.shift.end_shift + relativedelta(hours=7)).minute / 60

                        # Giờ overtime đăng ký (float giờ)
                        ot_start = x.start_time
                        ot_end = x.end_time

                        # Trường hợp overtime hoàn toàn trước ca
                        if (shift_start - 0.2) <= ot_end <= shift_start:
                            if record.check_in:
                                check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                                (record.check_in + relativedelta(hours=7)).minute / 60
                                actual_start = max(ot_start, check_in_time)
                                actual_end = ot_end
                                if record.check_out:
                                    check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                                     (record.check_out + relativedelta(hours=7)).minute / 60
                                    actual_end = min(actual_end, check_out_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                        # Trường hợp overtime hoàn toàn sau ca
                        elif shift_end <= ot_start <= (shift_end + 0.2):
                            if record.check_out:
                                check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                                 (record.check_out + relativedelta(hours=7)).minute / 60
                                actual_start = ot_start
                                actual_end = min(ot_end, check_out_time)
                                if record.check_in:
                                    check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                                    (record.check_in + relativedelta(hours=7)).minute / 60
                                    actual_start = max(actual_start, check_in_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                        # Trường hợp overtime nằm trong giờ ca (hoặc chồng 1 phần ca)
                        else:
                            # phần trước ca (nếu có)
                            if ot_start < shift_start:
                                actual_start = ot_start
                                if record.check_in:
                                    check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                                    (record.check_in + relativedelta(hours=7)).minute / 60
                                    actual_start = max(actual_start, check_in_time)
                                actual_end = min(ot_end, shift_start)
                                if record.check_out:
                                    check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                                     (record.check_out + relativedelta(hours=7)).minute / 60
                                    actual_end = min(actual_end, check_out_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                            # phần sau ca (nếu có)
                            if ot_end > shift_end:
                                actual_start = max(ot_start, shift_end)
                                if record.check_in:
                                    check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                                    (record.check_in + relativedelta(hours=7)).minute / 60
                                    actual_start = max(actual_start, check_in_time)
                                actual_end = ot_end
                                if record.check_out:
                                    check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                                     (record.check_out + relativedelta(hours=7)).minute / 60
                                    actual_end = min(actual_end, check_out_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                            # phần trong ca
                            inside_start = max(ot_start, shift_start)
                            inside_end = min(ot_end, shift_end)
                            if record.check_in:
                                check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                                (record.check_in + relativedelta(hours=7)).minute / 60
                                inside_start = max(inside_start, check_in_time)
                            if record.check_out:
                                check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                                 (record.check_out + relativedelta(hours=7)).minute / 60
                                inside_end = min(inside_end, check_out_time)
                            if inside_end > inside_start:
                                total_overtime += inside_end - inside_start

                    else:
                        # Nếu shift_ot = True → tính thẳng theo khoảng OT nhưng vẫn cắt theo check_in/check_out
                        if record.check_in and record.check_out:
                            check_in_time = (record.check_in + relativedelta(hours=7)).hour + \
                                            (record.check_in + relativedelta(hours=7)).minute / 60
                            check_out_time = (record.check_out + relativedelta(hours=7)).hour + \
                                             (record.check_out + relativedelta(hours=7)).minute / 60
                            actual_start = max(x.start_time, check_in_time)
                            actual_end = min(x.end_time, check_out_time)
                            if actual_end > actual_start:
                                total_overtime += actual_end - actual_start

            if record.shift.type_ot == 'nb':
                record.over_time_nb = total_overtime * record.shift.coefficient
                record.over_time = 0
            else:
                if record.weekday == '6' and record.employee_id.company_id.id == 16:
                    record.over_time = total_overtime * 2
                else:
                    record.over_time = total_overtime

    color = fields.Selection([
            ('red', 'Red'),
            ('green', 'Green'),
        ],
        string="Màu", compute="_compute_color"
    )

    @api.depends('date')
    def _get_month_year(self):
        for r in self:
            if r.date:
                r.month = r.date.month
                r.year = r.date.year
            else:
                r.month = None
                r.year = None

    @api.depends('employee_id', 'employee_id.department_id')
    def _get_department_id(self):
        for r in self:
            if r.employee_id.department_id:
                r.department_id = r.employee_id.department_id.id
            else:
                r.department_id = None

    # tạo ra bản ghi cho từng nhân viên trong các ngày của tháng

    def update_attendance_data(self):
        employees = self.env['hr.employee'].search([('id', '!=', 1)])
        current_date = datetime.now()
        start_date = current_date.replace(day=1) + timedelta(hours=7) - relativedelta(months=1)
        end_date = (start_date + relativedelta(months=2)) - timedelta(days=1)

        for employee in employees:
            for single_date in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1)):
                existing_record = self.env['employee.attendance'].search([
                    ('employee_id', '=', employee.id),
                    ('date', '=', single_date)
                ])
                if not existing_record:
                    self.env['employee.attendance'].create({
                        'employee_id': employee.id,
                        'date': single_date,
                    })

    #lấy thông tin ca của nhân viên để điền vào trường ca
    @api.depends('date', 'employee_id')
    def _get_shift_employee(self):
        for r in self:
            r.shift = None  # Gán mặc định để tránh lỗi nếu không tìm thấy

            if not r.date or not r.employee_id:
                continue

            # Tìm shift theo register.shift.rel
            shift = self.env['register.shift.rel'].sudo().search([
                ('register_shift.employee_id', '=', r.employee_id.id),
                ('date', '=', r.date)
            ], limit=1)

            # Nếu không tìm thấy shift, tìm trong register.work
            if not shift:
                shift_re = self.env['register.work'].sudo().search([
                    ('start_date', '<=', r.date),
                    ('end_date', '>=', r.date),
                    ('employee_id', 'in', [r.employee_id.id])
                ], limit=1)
                if shift_re:
                    shift = shift_re

            # Gán shift nếu tìm thấy
            if shift:
                r.shift = shift.shift.id
            elif r.employee_id.shift:
                r.shift = r.employee_id.shift.id

    #Lấy thông tin giờ phải check-in và giờ check-out của nhân viên
    @api.depends('shift')
    def _get_time_in_out(self):
        for r in self:
            # Nếu không có shift, gán giá trị mặc định và bỏ qua
            if not r.shift:
                r.time_check_in = None
                r.time_check_out = None
                continue

            # Tính toán các giá trị thời gian cơ bản
            time_ci = (r.shift.start + timedelta(hours=7)).time()
            time_co = (r.shift.end_shift + timedelta(hours=7)).time()
            date = r.date
            check_time_ci = datetime.combine(date, time_ci)
            check_time_co = datetime.combine(date, time_co)

            # Tính thời gian check-in
            time_check_in = check_time_ci - timedelta(hours=7, minutes=r.shift.earliest)

            # Tính thời gian check-out
            time_check_out = check_time_co + timedelta(hours=-7, minutes=r.shift.latest_out)

            # Xử lý trường hợp night shift
            if r.shift.night:
                # Nếu ngày của check-in và check-out giống nhau, điều chỉnh thời gian check-out qua ngày hôm sau
                if (time_check_in + timedelta(hours=7)).date() == (time_check_out + timedelta(hours=7)).date():
                    time_check_out += timedelta(days=1)
            overtime = self.env['register.overtime'].sudo().search([('employee_id', '=', r.employee_id.id),
                                                                    ('start_date', '<=', r.date),
                                                                    ('end_date', '>=', r.date)])
            overtime_update = self.env['overtime.rel'].sudo().search([('date', '=', r.date),
                                                               ('overtime_id.status', '=', 'done')])
            overtime_update = overtime_update.filtered(lambda x: (x.overtime_id.employee_id and x.overtime_id.employee_id.id == r.employee_id.id)
                                                   or (x.overtime_id.employee_ids and r.employee_id.id in x.overtime_id.employee_ids.ids))
            if overtime:
                for ot in overtime:
                    start = int(ot.start_time)
                    end = int(ot.end_time)
                    if end == r.shift.start.hour + 7:
                        time_check_in = time_check_in - timedelta(hours=end - start)
                    if start == r.shift.end_shift.hour + 7:
                        time_check_out = time_check_out + timedelta(hours=end - start)

            if overtime_update:
                for ot_update in overtime_update:
                    start = int(ot_update.start_time)
                    end = int(ot_update.end_time)
                    if end == r.shift.start.hour + 7:
                        time_check_in = time_check_in - timedelta(hours=end - start)
                    if start == r.shift.end_shift.hour + 7:
                        time_check_out = time_check_out + timedelta(hours=end - start)

            # Gán kết quả
            r.time_check_in = time_check_in
            r.time_check_out = time_check_out

   #Lấy ra thông tin số giờ cần có mặt theo ca
    @api.depends('shift')
    def _get_duration(self):
        for r in self:
            if r.shift:
                start_time = r.shift.start.time()
                end_time = r.shift.end_shift.time()
                start_seconds = timedelta(hours=start_time.hour, minutes=start_time.minute,
                                          seconds=start_time.second).total_seconds()
                end_seconds = timedelta(hours=end_time.hour, minutes=end_time.minute,
                                        seconds=end_time.second).total_seconds()
                hours_difference = (end_seconds - start_seconds) / 3600.0
                r.duration = abs(hours_difference)
            else:
                r.duration = 0

    #Lấy giờ mốc để tách giờ check-in và giờ check-out của nhân viên
    @api.depends('shift', 'duration', 'time_check_in', 'time_check_out')
    def _check_no_in_out(self):
        for r in self:
            r.check_no_in = None
            r.check_no_out = None
            if r.shift and r.duration > 0 and r.time_check_in and r.time_check_out:
                duration = r.duration / 2
                r.check_no_in = r.time_check_in + timedelta(minutes=r.shift.earliest + r.shift.latest)
                r.check_no_out = r.time_check_out - timedelta(hours=duration, minutes=r.shift.latest_out)

    #Lấy thông tin check-in và check-out của nhân viên
    @api.depends('employee_id', 'time_check_in', 'time_check_out', 'check_no_in', 'check_no_out')
    def _get_check_in_out(self):
        def calculate_time(input_time, date, default_time):
            if not isinstance(input_time, (int, float)) or input_time < 0:
                raise ValueError(f"Invalid time value: {input_time}")

            hour = int(input_time)
            minute = int((input_time % 1) * 60)
            if 0 <= hour < 24:
                return datetime.combine(date, time(hour, minute, 0))
            else:
                return default_time

        for r in self:
            r.check_in, r.check_out = None, None
            if not r.time_check_in or not r.time_check_out or not r.employee_id:
                continue

            # Lấy attendance_times từ cơ sở dữ liệu
            attendance_times = self.env['master.data.attendance'].sudo().search_read(
                [('attendance_time', '>=', r.time_check_in),
                 ('attendance_time', '<=', r.time_check_out),
                 ('employee_id', '=', r.employee_id.id)],
                ['attendance_time'],
                order='attendance_time ASC'
            )

            # Tách dữ liệu check_in và check_out
            attendance_ci = [a['attendance_time'] for a in attendance_times if a['attendance_time'] and r.check_no_in and a['attendance_time'] <= r.check_no_in]
            attendance_co = [a['attendance_time'] for a in attendance_times if a['attendance_time'] and r.check_no_out and a['attendance_time'] >= r.check_no_out]

            check_in = attendance_ci[0] if attendance_ci else None
            check_out = attendance_co[-1] if attendance_co else None

            r.check_in = check_in
            r.check_out = check_out

            # Xử lý in_outs
            in_outs = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('type.date_and_time', '=', 'time'),
                ('word_slip.status', '=', 'done')
            ])

            in_outs = in_outs.filtered(
                lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (
                            x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            for in_out in in_outs:
                if in_out and in_out.time_to:
                    ci = calculate_time(in_out.time_to, r.date, datetime.combine(r.date, time(0, 0, 0)))
                    ci = ci - relativedelta(hours=7)

                    if not check_in and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci
                    elif check_in and check_in > ci and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci

                if in_out and in_out.time_from:
                    co = calculate_time(in_out.time_from, r.date, datetime.combine(r.date, time(0, 0, 0)))
                    co = co - relativedelta(hours=7)

                    if not check_out and r.check_no_out and r.time_check_out and r.check_no_out <= co <= r.time_check_out:
                        r.check_out = co
                    elif check_out and check_out < co and r.check_no_out and r.time_check_out and r.check_no_out <= co <= r.time_check_out:
                        r.check_out = co

    #Lấy thông tin xem nhân viên có check-in hay check-out hay không
    def _get_attendance(self):
        for r in self:
            if (not r.check_in and not r.check_out) or (r.check_in and r.check_out):
                r.note = None
            elif not r.check_in:
                r.note = 'no_in'
            elif not r.check_out:
                r.note = 'no_out'

            if not r.shift:
                r.note = 'no_shift'

            if r.leave > 0 or r.compensatory > 0 or r.vacation > 0:
                r.note = None

    #Lấy thông tin số phút nhân viên đi muộn hoặc về sớm
    def _get_minute_late_early(self):
        for r in self:
            # Khởi tạo giá trị mặc định
            r.minutes_late, r.minutes_early = 0, 0

            if not r.shift:
                continue

            # Tính thời gian bắt đầu và kết thúc ca làm việc
            shift_start_time = datetime.combine(r.date, r.shift.start.time()) + timedelta(hours=7)
            shift_end_time = datetime.combine(r.date, r.shift.end_shift.time()) + timedelta(hours=7)

            if r.check_in:
                check_in_time = r.check_in + timedelta(hours=7)
                if check_in_time.time() > shift_start_time.time():
                    minute_late = (check_in_time - datetime.combine(check_in_time.date(), shift_start_time.time())).total_seconds() / 60
                    r.minutes_late = int(minute_late)

            if r.check_out:
                check_out_time = r.check_out + timedelta(hours=7)
                if check_out_time < shift_end_time:
                    hour = shift_end_time.time().hour
                    minute = shift_end_time.time().minute
                    second = shift_end_time.time().second
                    if hour == 0:
                        shift_end_in_hours = 24.0
                    else:
                        shift_end_in_hours = hour + minute / 60 + second / 3600
                    checkout_hour = check_out_time.hour + check_out_time.minute / 60 + check_out_time.second / 3600

                    minute_early = (shift_end_in_hours - checkout_hour) * 60
                    r.minutes_early = int(minute_early)
            if r.leave > 0 or r.compensatory > 0 or r.vacation > 0:
                r.minutes_early = 0
                r.minutes_late = 0

            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]

            if (r.shift.shift_ot) or (r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1))):
                r.minutes_early = 0
                r.minutes_late = 0
            else:
                pass

    #Lấy thông tin ngày công của nhân viên
    @api.depends('check_in', 'check_out', 'shift')
    def _get_work_day(self):
        for r in self:
            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]
            free_time = self.env['free.timekeeping'].sudo().search([('employee_id', '=', r.employee_id.id),
                                                                    ('state', '=', 'active'),
                                                                    ('start_date', '<=', r.date),
                                                                    ('end_date', '>=', r.date)])

            leave_no_work = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('word_slip.status', '=', 'done'),
                ('word_slip.type.key', '=', "KL"),
            ])

            leave_no_work = leave_no_work.filtered(
                lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (
                            x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            if r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.work_day = 0
            elif r.shift.shift_ot:
                r.work_day = 0
            else:
                if free_time:
                    if r.compensatory > 0:
                        r.work_day = 1 - r.compensatory
                    elif r.leave > 0:
                        r.work_day = 1 - r.leave
                    else:
                        r.work_day = 1
                else:
                    if r.shift.half_shift == True:
                        if r.check_in and r.check_out:
                            r.work_day = 0.5
                        else:
                            r.work_day = 0
                    else:
                        if r.check_in and r.check_out:
                            if r.compensatory > 0:
                                r.work_day = 1 - r.compensatory
                            elif r.leave > 0:
                                r.work_day = 1 - r.leave
                            else:
                                r.work_day = 1
                        elif r.check_in and not r.check_out:
                            if r.compensatory > 0:
                                r.work_day = 1 - r.compensatory
                            elif r.leave > 0:
                                r.work_day = 1 - r.leave
                            elif leave_no_work:
                                r.work_day = 0.5
                            else:
                                r.work_day = 0
                        elif not r.check_in and r.check_out:
                            if r.compensatory > 0:
                                r.work_day = 1 - r.compensatory
                            elif r.leave > 0:
                                r.work_day = 1 - r.leave
                            elif leave_no_work:
                                r.work_day = 0.5
                            else:
                                r.work_day = 0
                        else:
                            r.work_day = 0


    # tính thứ cho ngày
    @api.depends('date')
    def _compute_weekday(self):
        for r in self:
            if r.date:
                weekday = r.date.weekday()
                r.weekday = str(weekday)
            else:
                r.weekday = None

    # tính màu cho danh sách
    @api.depends('date','check_in','check_out', 'minutes_late', 'minutes_early')
    def _compute_color(self):
        today = date.today()
        for r in self:
            r.color = None

            if not r.date or r.date > today:
                continue

            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]

            # Tính toán số ngày nghỉ (on_leave)
            word_slips = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('type.date_and_time', '=', 'date'),
                ('word_slip.status', '=', 'done')
            ])
            word_slips = word_slips.filtered(
                lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (
                        x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))
            on_leave = 0
            if word_slips:
                for slip in word_slips:
                    if slip.start_time == slip.end_time:
                        on_leave += 0.5
                    elif slip.start_time == 'first_half' and slip.end_time == 'second_half':
                        on_leave += 1

            # Tổng số công (tong_cong)
            tong_cong = on_leave + r.public_leave + r.work_day

            # Xác định màu sắc
            if tong_cong >= 1 and r.minutes_late == 0 and r.minutes_early == 0:
                r.color = 'green'
            else:
                r.color = 'red'

            if r.shift.half_shift:
                if tong_cong >= 0.5 and r.minutes_late == 0 and r.minutes_early == 0:
                    r.color = 'green'
                else:
                    r.color = 'red'
            else:
                pass

            if weekday == 6 or (weekday == 5 and week_number % 2 == 1):
                if tong_cong == 0 or r.employee_id.company_id.calender_work != 'odd':
                    r.color = None
                elif r.over_time != 0:
                    if r.minutes_late == 0 and r.minutes_early == 0:
                        r.color = 'green'
                    else:
                        r.color = 'red'

            if r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.color = None
            else:
                pass
            if (r.employee_id.company_id.calender_work != 'odd' and (weekday == 6 or weekday == 5)):
                r.color = None

    @api.depends('minutes_late', 'minutes_early')
    def get_times_late(self):
        for r in self:
            r.times_late = 0
            if r.minutes_late >= 31:
                r.times_late = 1
            if r.minutes_early >= 31:
                r.times_late += 1

    @api.depends('shift', 'work_day')
    def _get_actual_work(self):
        for r in self:
            if r.shift and r.work_day:
                r.actual_work = r.work_day * r.shift.recent_work
            else:
                r.actual_work = 0

    @api.depends('note')
    def _get_forgot_time(self):
        for r in self:
            r.forgot_time = 0
            if r.note == 'no_in' or r.note == 'no_out':
                r.forgot_time = 1

    @api.depends('work_day')
    def _get_work_eat(self):
        for r in self:
            r.work_eat = 0
            if r.work_day >= 1:
                r.work_eat = 1

    def send_fcm_notification(self, title, content, token, user_id, type, employee_id, application_id, screen="/notification", badge=1):
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
                   'employeeid': str(employee_id),
                   'body': content,
                   'datetime': str(datetime.now())
               })
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def noti_miss_work(self):
        self.with_delay().queue_job_miss_work()

    def queue_job_miss_work(self):
        today = date.today()
        today_str = today.strftime("%d/%m/%y")
        list_record = self.sudo().search([('date', '=', today),
                                          ('note', '!=', None)])
        for r in list_record:
            self.send_fcm_notification(
                title="Sơn Hà HRM",
                content="Bạn đang thiếu dữ liệu công ngày " + str(today_str) + " vui lòng kiểm tra lại!",
                token=r.employee_id.user_id.token,
                user_id=r.employee_id.user_id.id,
                type=3,
                employee_id=r.employee_id.id,
                application_id=0,
            )
