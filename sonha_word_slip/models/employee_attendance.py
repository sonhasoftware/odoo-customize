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

    month = fields.Integer("Tháng", compute="_get_month_year")
    year = fields.Integer("Năm", compute="_get_month_year")
    over_time = fields.Float("Giờ làm thêm", compute="get_hours_reinforcement")
    leave = fields.Float("Nghỉ phép", compute="_get_time_off")
    compensatory = fields.Float("Nghỉ bù", compute="_get_time_off")
    public_leave = fields.Float("Nghỉ lễ", cumpute="_get_time_off")

    @api.depends('employee_id', 'date')
    def _get_time_off(self):
        for r in self:
            on_leave = 0
            on_compensatory = 0

            # Lấy danh sách word slips liên quan
            word_slips = self.env['word.slip'].sudo().search([
                ('employee_id', '=', r.employee_id.id),
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date)
            ])

            for slip in word_slips:
                type_name = slip.word_slip.type.name.lower()  # Đưa về chữ thường để tránh lỗi so sánh
                if type_name == "nghỉ phép":
                    if slip.start_time == slip.end_time:
                        on_leave = 0.5
                    elif slip.start_time == 'first_half' and slip.end_time == 'second_half':
                        on_leave = 1
                elif type_name == "nghỉ bù":
                    if slip.start_time == slip.end_time:
                        on_compensatory = 0.5
                    elif slip.start_time == 'first_half' and slip.end_time == 'second_half':
                        on_compensatory = 1

            # Gán giá trị vào bản ghi
            r.leave = on_leave
            r.compensatory = on_compensatory

            public_leave = self.env['resource.calendar.leaves'].sudo().search([])
            public_leave = public_leave.filtered(
                lambda x: x.date_from.date() <= r.date <= x.date_to.date())
            if public_leave:
                r.public_leave = 1
            else:
                r.public_leave = 0

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
            shift = self.env['register.shift.rel'].sudo().search([('register_shift.employee_id', '=', r.employee_id.id),
                                                                  ('date', '=', r.date)])
            shift_re = self.env['register.work'].sudo().search([('start_date', '<=', r.date),
                                                                ('end_date', '>=', r.date)])
            shift_re = shift_re.filtered(lambda x: r.employee_id.id in x.employee_id.ids)
            if shift:
                r.shift = shift.shift.id
            elif shift_re:
                r.shift = shift_re[0].shift.id
            elif r.employee_id.shift:
                r.shift = r.employee_id.shift.id
            else:
                r.shift = None

    #Lấy thông tin giờ phải check-in và giờ check-out của nhân viên
    @api.depends('shift')
    def _get_time_in_out(self):
        for r in self:
            if r.shift:
                time_ci = (r.shift.start + timedelta(hours=7)).time()
                time_co = (r.shift.end_shift + timedelta(hours=7)).time()
                date = r.date
                check_time_ci = datetime.combine(date, time_ci)
                check_time_co = datetime.combine(date, time_co)
                if not r.shift.night:
                    r.time_check_in = check_time_ci - timedelta(hours=7, minutes=r.shift.earliest)
                    r.time_check_out = check_time_co + timedelta(hours=-7, minutes=r.shift.latest_out)
                if r.shift.night:
                    r.time_check_in = check_time_ci - timedelta(hours=7, minutes=r.shift.earliest)
                    check_out = check_time_co + timedelta(hours=-7, minutes=r.shift.latest_out)
                    if (r.time_check_in + timedelta(hours=7)).date() == (check_out + timedelta(hours=7)).date():
                        r.time_check_out = check_out + timedelta(days=1)
                    else:
                        r.time_check_out = check_out
            else:
                r.time_check_in = None
                r.time_check_out = None

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
            if r.shift and r.duration > 0 and r.time_check_in and r.time_check_out:
                duration = r.duration / 2
                r.check_no_in = r.time_check_in + timedelta(hours=duration, minutes=r.shift.earliest)
                r.check_no_out = r.time_check_out - timedelta(hours=duration, minutes=r.shift.latest_out)
            else:
                r.check_no_in = None
                r.check_no_out = None

    #Lấy thông tin check-in và check-out của nhân viên
    @api.depends('employee_id', 'time_check_in', 'time_check_out', 'check_no_in', 'check_no_out')
    def _get_check_in_out(self):
        for r in self:
            attendance_times = self.env['master.data.attendance'].sudo().search_read(
                [('attendance_time', '>=', r.time_check_in),
                 ('attendance_time', '<=', r.time_check_out),
                 ('employee_id', '=', r.employee_id.id)],
                ['attendance_time'],
                order='attendance_time ASC'
            )

            # Phân tách attendance_times thành check_in và check_out
            attendance_ci = [a['attendance_time'] for a in attendance_times if a['attendance_time'] <= r.check_no_in]
            attendance_co = [a['attendance_time'] for a in attendance_times if a['attendance_time'] >= r.check_no_out]

            r.check_in = attendance_ci[0] if attendance_ci else None
            r.check_out = attendance_co[-1] if attendance_co else None

            in_outs = self.env['word.slip'].sudo().search([('employee_id', '=', r.employee_id.id),
                                                          ('from_date', '<=', r.date),
                                                          ('to_date', '>=', r.date)])
            if in_outs:
                for in_out in in_outs:
                    if in_out and in_out.time_to:
                        hour = int(in_out.time_to) - 7
                        minute = int((in_out.time_to % 1) * 60)
                        if 0 <= hour <= 23:
                            ci = datetime.combine(r.date, time(hour, minute, 0))
                        else:
                            ci = datetime.combine(r.date, time(0, 0, 0))
                        if not r.check_in or r.check_in.time() > ci.time():
                            r.check_in = ci
                        elif r.check_in.time() > ci.time():
                            r.check_in = ci
                        elif r.check_in.time() < ci.time():
                            r.check_in = r.check_in
                    if in_out and in_out.time_from:
                        # Kiểm tra giá trị đầu vào
                        if not (isinstance(in_out.time_from, (int, float)) and in_out.time_from >= 0):
                            raise ValueError(f"Invalid time_from value: {in_out.time_from}")

                        # Tính toán giờ và phút
                        hour = int(in_out.time_from) - 7
                        minute = int((in_out.time_from % 1) * 60)

                        # Giới hạn giá trị 'hour' trong phạm vi hợp lệ
                        hour = max(0, min(hour, 23))

                        # Tạo datetime cho check-out
                        co = datetime.combine(r.date, time(hour, minute, 0))

                        # Gán giá trị check-out
                        if not r.check_out:
                            r.check_out = co
                        elif r.check_out.time() < co.time():
                            r.check_out = co
                        elif r.check_out.time() > co.time():
                            r.check_out = r.check_out

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
            if r.shift:
                if r.check_in and (r.check_in + timedelta(hours=7)).time() > (r.shift.start + timedelta(hours=7)).time():
                    check_in_time = datetime.combine(r.check_in.date(), r.check_in.time())
                    shift_start_time = datetime.combine(r.check_in.date(), r.shift.start.time())

                    minute_late = (check_in_time + timedelta(hours=7)) - (shift_start_time + timedelta(hours=7))
                    r.minutes_late = int(minute_late.total_seconds() / 60)
                else:
                    r.minutes_late = 0
                if r.check_out and (r.check_out + timedelta(hours=7)).time() < (r.shift.end_shift + timedelta(hours=7)).time():
                    check_out_time = datetime.combine(r.check_out.date(), r.check_out.time())
                    shift_end_time = datetime.combine(r.check_out.date(), r.shift.end_shift.time())

                    minute_early = (shift_end_time + timedelta(hours=7)) - (check_out_time + + timedelta(hours=7))
                    r.minutes_early = int(minute_early.total_seconds() / 60)
                else:
                    r.minutes_early = 0
            else:
                r.minutes_late = 0
                r.minutes_early = 0

    #Lấy thông tin ngày công của nhân viên
    def _get_work_day(self):
        for r in self:
            # work_leave = self.env['word.slip'].sudo().search([
            #     ('employee_id', '=', r.employee_id.id),
            #     ('from_date', '<=', r.date),
            #     ('to_date', '>=', r.date),
            # ])
            # work_leave = work_leave.filtered(lambda x: x.type.paid == True)
            # public_holiday = self.env['resource.calendar.leaves'].sudo().search([])
            # public_holiday = public_holiday.filtered(lambda x: x.date_from.date() <= r.date <= x.date_to.date())
            # if public_holiday:
            #     r.work_day = 1
            # elif work_leave:
            #     r.work_day = 1
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
            
            if r.date and r.date <= today:
                weekday = r.date.weekday()
                week_number = r.date.isocalendar()[1]

                if weekday == 6 or (weekday == 5 and week_number % 2 == 1):
                    r.color = None
                elif not (r.check_in and r.check_out) or r.minutes_late != 0 or r.minutes_early != 0:
                    r.color = 'red'
                else:
                    r.color = 'green'