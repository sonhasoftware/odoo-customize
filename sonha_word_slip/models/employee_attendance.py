from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


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
                             ('no_out', "Không có check out")],
                            string="Ghi chú",
                            compute="_get_attendance")
    work_day = fields.Float("Ngày công", compute="_get_work_day")
    minutes_late = fields.Float("Số phút đi muộn", compute="_get_minute_late_early")
    minutes_early = fields.Float("Số phút về sớm", compute="_get_minute_late_early")

    month = fields.Integer("Tháng", compute="_get_month_year", store=True)
    year = fields.Integer("Năm", compute="_get_month_year")
    over_time = fields.Float("Giờ làm thêm", compute="get_hours_reinforcement")
    leave = fields.Float("Nghỉ phép", compute="_get_time_off")
    compensatory = fields.Float("Nghỉ bù", compute="_get_time_off")
    public_leave = fields.Float("Nghỉ lễ", cumpute="_get_time_off")
    c2k3 = fields.Float("Ca 2 kíp 3", compute="get_shift")
    c3k4 = fields.Float("Ca 3 kíp 4", compute="get_shift")

    @api.depends('shift')
    def get_shift(self):
        for r in self:
            # Reset giá trị mặc định
            r.c2k3 = 0
            r.c3k4 = 0

            # Nếu shift tồn tại, kiểm tra các điều kiện
            if r.shift:
                r.c2k3 = 1 if r.shift.c2k3 else 0
                r.c3k4 = 1 if r.shift.c3k4 else 0

    @api.depends('employee_id', 'date')
    def _get_time_off(self):
        # Lấy tất cả public leaves một lần, giảm số lần truy vấn
        all_public_leaves = self.env['resource.calendar.leaves'].sudo().search([])

        for r in self:
            # Khởi tạo giá trị mặc định
            r.leave = 0
            r.compensatory = 0
            r.public_leave = 0

            if not r.employee_id or not r.date:
                continue

            # Tìm tất cả các word.slip liên quan
            word_slips = self.env['word.slip'].sudo().search([
                ('employee_id', '=', r.employee_id.id),
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date)
            ])

            # Xử lý word.slip
            for slip in word_slips:
                type_name = slip.word_slip.type.name.lower()  # Chuyển về chữ thường
                if type_name == "nghỉ phép":
                    r.leave = 0.5 if slip.start_time == slip.end_time else 1
                elif type_name == "nghỉ bù":
                    r.compensatory = 0.5 if slip.start_time == slip.end_time else 1

            # Kiểm tra public leave
            if all_public_leaves.filtered(
                    lambda leave: leave.date_from.date() <= r.date <= leave.date_to.date()):
                r.public_leave = 1

    @api.depends('employee_id', 'date')
    def get_hours_reinforcement(self):
        for record in self:
            overtime = 0
            ot = self.env['register.overtime'].sudo().search([('employee_id', '=', record.employee_id.id),
                                                              ('start_date', '<=', record.date),
                                                              ('end_date', '>=', record.date)])
            if ot:
                for r in ot:
                    overtime += r.end_time - r.start_time
            record.over_time = overtime

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


    @api.depends('employee_id')
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
                r.check_no_in = r.time_check_in + timedelta(hours=duration, minutes=r.shift.earliest)
                r.check_no_out = r.time_check_out - timedelta(hours=duration, minutes=r.shift.latest_out)

    #Lấy thông tin check-in và check-out của nhân viên
    @api.depends('employee_id', 'time_check_in', 'time_check_out', 'check_no_in', 'check_no_out')
    def _get_check_in_out(self):
        def calculate_time(input_time, date, default_time):
            """Tính toán và trả về datetime từ giờ/phút, hoặc trả về giá trị mặc định."""
            if not isinstance(input_time, (int, float)) or input_time < 0:
                raise ValueError(f"Invalid time value: {input_time}")
            hour = max(0, min(int(input_time) - 7, 23))  # Giới hạn giờ trong phạm vi 0-23
            minute = int((input_time % 1) * 60)
            return datetime.combine(date, time(hour, minute, 0)) if 0 <= hour <= 23 else default_time

        for r in self:
            # Kiểm tra và gán giá trị mặc định cho check_in, check_out
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
            attendance_ci = [a['attendance_time'] for a in attendance_times if a['attendance_time'] <= r.check_no_in]
            attendance_co = [a['attendance_time'] for a in attendance_times if a['attendance_time'] >= r.check_no_out]

            check_in = attendance_ci[0] if attendance_ci else None
            check_out = attendance_co[-1] if attendance_co else None

            r.check_in = check_in
            r.check_out = check_out

            # Xử lý in_outs
            in_outs = self.env['word.slip'].sudo().search([
                ('employee_id', '=', r.employee_id.id),
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date)
            ])

            for in_out in in_outs:
                if in_out and in_out.time_to:
                    ci = calculate_time(in_out.time_to, r.date, datetime.combine(r.date, time(0, 0, 0)))

                    if not check_in and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci
                    elif check_in and check_in > ci and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci

                if in_out and in_out.time_from:
                    co = calculate_time(in_out.time_from, r.date, datetime.combine(r.date, time(0, 0, 0)))

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

    #Lấy thông tin số phút nhân viên đi muộn hoặc về sớm
    def _get_minute_late_early(self):
        for r in self:
            # Khởi tạo giá trị mặc định
            r.minutes_late, r.minutes_early = 0, 0

            if not r.shift:
                continue

            # Tính thời gian bắt đầu và kết thúc ca làm việc
            shift_start_time = r.shift.start + timedelta(hours=7)
            shift_end_time = r.shift.end_shift + timedelta(hours=7)

            if r.check_in:
                check_in_time = r.check_in + timedelta(hours=7)
                if check_in_time.time() > shift_start_time.time():
                    minute_late = (check_in_time - datetime.combine(check_in_time.date(), shift_start_time.time())).total_seconds() / 60
                    r.minutes_late = int(minute_late)

            if r.check_out:
                check_out_time = r.check_out + timedelta(hours=7)
                if check_out_time.time() < shift_end_time.time():
                    minute_early = (datetime.combine(check_out_time.date(),
                                                     shift_end_time.time()) - check_out_time).total_seconds() / 60
                    r.minutes_early = int(minute_early)

    #Lấy thông tin ngày công của nhân viên
    @api.depends('check_in', 'check_out')
    def _get_work_day(self):
        for r in self:
            if r.check_in and r.check_out:
                r.work_day = 1
            elif r.check_in and not r.check_out:
                r.work_day = 0.5
            elif not r.check_in and r.check_out:
                r.work_day = 0.5
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
                ('employee_id', '=', r.employee_id.id),
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('type.date_and_time', '=', 'date')
            ])
            on_leave = sum(
                0.5 if slip.start_time == slip.end_time else 1
                for slip in word_slips
                if slip.start_time == 'first_half' and slip.end_time == 'second_half'
                or slip.start_time != slip.end_time
            )

            # Tổng số công (tong_cong)
            tong_cong = on_leave + r.public_leave + r.work_day

            # Xác định màu sắc
            if tong_cong >= 1 and r.minutes_late == 0 and r.minutes_early == 0:
                r.color = 'green'
            else:
                r.color = 'red'

            # Xử lý điều kiện đặc biệt cho cuối tuần
            if weekday == 6 or (weekday == 5 and week_number % 2 == 1):
                if r.over_time != 0:
                    if r.minutes_late == 0 and r.minutes_early == 0 :
                        r.color = 'green'
                    else :
                        r.color = 'red'
                elif tong_cong == 0:
                    r.color = None
