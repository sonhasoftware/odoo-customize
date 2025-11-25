# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from datetime import datetime, time, timedelta, date
import requests
import json


class EmployeeAttendanceV2(models.Model):
    _name = 'employee.attendance.v2'
    _description = 'Bảng công chi tiết'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban',
                                    compute="_compute_department_id", store=True)
    date = fields.Date(string='Ngày', required=True, store=True)
    weekday = fields.Selection([
        ('0', 'Thứ hai'), ('1', 'Thứ ba'), ('2', 'Thứ tư'),
        ('3', 'Thứ năm'), ('4', 'Thứ sáu'), ('5', 'Thứ bảy'),
        ('6', 'Chủ nhật')
    ], string="Thứ", compute="_compute_weekday", store=True)

    check_in = fields.Datetime(string='Giờ vào', compute="_compute_check_in_out", store=True)
    check_out = fields.Datetime(string='Giờ ra', compute="_compute_check_in_out", store=True)
    duration = fields.Float("Giờ công", compute="_compute_duration", store=True)

    shift = fields.Many2one('config.shift', string="Ca làm việc",
                            compute="_compute_shift_employee", store=True)
    time_check_in = fields.Datetime("Thời gian phải vào", compute="_compute_time_in_out", store=True)
    time_check_out = fields.Datetime("Thời gian phải ra", compute="_compute_time_in_out", store=True)
    check_no_in = fields.Datetime("Check không có check_in", compute="_compute_no_in_out", store=True)
    check_no_out = fields.Datetime("Check không có check_out", compute="_compute_no_in_out", store=True)

    note = fields.Selection([
        ('no_in', "Không có check in"),
        ('no_out', "Không có check out"),
        ('no_shift', "Không có ca làm việc")
    ], string="Ghi chú", compute="_compute_attendance", store=True)

    work_day = fields.Float("Ngày công", compute="_compute_work_day", store=True)
    minutes_late = fields.Float("Số phút đi muộn", compute="_compute_minutes_late_early", store=True)
    minutes_early = fields.Float("Số phút về sớm", compute="_compute_minutes_late_early", store=True)

    month = fields.Integer("Tháng", compute="_compute_month_year", store=True)
    year = fields.Integer("Năm", compute="_compute_month_year", store=True)

    over_time = fields.Float("Giờ làm thêm", compute="_compute_hours_reinforcement", store=True)
    over_time_nb = fields.Float("Làm thêm hưởng NB", compute="_compute_hours_reinforcement", store=True)

    leave = fields.Float("Nghỉ phép", compute="_compute_time_off", store=True)
    compensatory = fields.Float("Nghỉ bù", compute="_compute_time_off", store=True)
    public_leave = fields.Float("Nghỉ lễ", compute="_compute_time_off", store=True)
    vacation = fields.Float("Nghỉ mát", compute="_compute_time_off", store=True)

    c2k3 = fields.Float("Ca 2 kíp 3", compute="_compute_shift_flags", store=True)
    c3k4 = fields.Float("Ca 3 kíp 4", compute="_compute_shift_flags", store=True)
    shift_toxic = fields.Float("Ca độc hại", compute="_compute_shift_flags", store=True)

    work_hc = fields.Float("Công hành chính", compute="_compute_work_hc_sp", store=True)
    work_sp = fields.Float("Công Sản phẩm", compute="_compute_work_hc_sp", store=True)

    times_late = fields.Integer("Đi muộn quá 30p", compute="_compute_times_late", store=True)
    work_calendar = fields.Boolean("Lịch làm việc", compute="_compute_work_calendar", store=True)

    actual_work = fields.Float("Công thực tế theo ca", compute="_compute_actual_work", store=True)

    forgot_time = fields.Integer("Quên CI/CO", compute="_compute_forgot_time", store=True)
    work_eat = fields.Integer("Công ăn", compute="_compute_work_eat", store=True)

    color = fields.Selection([('red', 'Red'), ('green', 'Green')], string="Màu", compute="_compute_color", store=True)

    # ---------------------- COMPUTE FUNCTIONS ----------------------

    @api.depends('date', 'employee_id')
    def _compute_department_id(self):
        for rec in self:
            rec.department_id = rec.employee_id.department_id.id if rec.employee_id and rec.employee_id.department_id else None

    @api.depends('date')
    def _compute_weekday(self):
        for rec in self:
            rec.weekday = str(rec.date.weekday()) if rec.date else None

    @api.depends('date', 'shift')
    def _compute_work_calendar(self):
        for r in self:
            r.work_calendar = True
            if not r.date:
                continue
            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]
            if r.shift and r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.work_calendar = False

    @api.depends('shift', 'work_day')
    def _compute_work_hc_sp(self):
        for r in self:
            r.work_sp = 0
            r.work_hc = 0
            if r.shift and r.shift.type_shift == 'sp':
                r.work_sp = r.work_day
            else:
                r.work_hc = r.work_day

    @api.depends('shift')
    def _compute_shift_flags(self):
        for r in self:
            r.c2k3 = 0
            r.c3k4 = 0
            r.shift_toxic = 0
            if r.shift:
                r.c2k3 = 1 if getattr(r.shift, 'c2k3', False) else 0
                r.c3k4 = 1 if getattr(r.shift, 'c3k4', False) else 0
                r.shift_toxic = r.work_day if getattr(r.shift, 'shift_toxic', False) else 0

    # ---------- Time-off: tích hợp word.slip + public leaves ----------
    @api.depends('employee_id', 'date')
    def _compute_time_off(self):
        # Lấy public leaves 1 lần để giảm truy vấn
        all_public_leaves = self.env['resource.calendar.leaves'].sudo().search([])

        for r in self:
            r.leave = r.compensatory = r.public_leave = r.vacation = 0.0
            if not r.employee_id or not r.date:
                continue

            # Tìm word.slip liên quan ngày đó & trạng thái done
            # lấy các slip có employee chính hoặc employee_ids chứa employee
            slips = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('word_slip.status', '=', 'done'),
            ])
            # filter theo employee quan tâm
            slips = slips.filtered(lambda s: (s.word_slip.employee_id and s.word_slip.employee_id.id == r.employee_id.id)
                                          or (s.word_slip.employee_ids and r.employee_id.id in s.word_slip.employee_ids.ids))

            for slip in slips:
                # Cẩn trọng field paths: giữ logic cũ
                t_name = (slip.word_slip.type.name or '').lower() if slip.word_slip and slip.word_slip.type else ''
                t_key = (slip.word_slip.type.key or '').lower() if slip.word_slip and slip.word_slip.type else ''
                # Nghỉ phép
                if t_name == "nghỉ phép":
                    if slip.start_time and slip.end_time:
                        r.leave = 1 if slip.start_time != slip.end_time else 0.5
                elif t_name == "nghỉ bù":
                    if slip.start_time and slip.end_time:
                        r.compensatory = 1 if slip.start_time != slip.end_time else 0.5
                elif t_key == "tbd":
                    if slip.start_time and slip.end_time:
                        r.vacation = 1 if slip.start_time != slip.end_time else 0.5

            # public leave check
            if all_public_leaves.filtered(lambda l: l.date_from.date() <= r.date <= l.date_to.date()):
                r.public_leave = 1

    # ---------- OVERTIME logic (giữ nguyên thuật toán, tối ưu helper) ----------
    @api.depends('employee_id', 'date', 'check_in', 'check_out', 'shift', 'weekday')
    def _compute_hours_reinforcement(self):
        for record in self:
            record.over_time_nb = 0.0
            record.over_time = 0.0
            if not record.employee_id or not record.date:
                continue

            # tìm register.overtime (ot) áp dụng cho employee/date
            ot_regs = self.env['register.overtime'].sudo().search([
                ('employee_id', '=', record.employee_id.id),
                ('start_date', '<=', record.date),
                ('end_date', '>=', record.date),
                ('status', '=', 'done')
            ])

            # tìm overtime.rel (overtime) cho date, lọc theo employee
            overtime_rels = self.env['overtime.rel'].sudo().search([
                '&',
                ('date', '=', record.date),
                '|',
                ('overtime_id.status', '=', 'done'),
                ('overtime_id.status_lv2', '=', 'done'),
            ])
            overtime_rels = overtime_rels.filtered(
                lambda x: (x.overtime_id.employee_id and x.overtime_id.employee_id.id == record.employee_id.id)
                          or (x.overtime_id.employee_ids and record.employee_id.id in x.overtime_id.employee_ids.ids)
            )

            def _dt_to_float_local(dt):
                if not dt:
                    return None
                dt_local = dt + relativedelta(hours=7)
                fl = dt_local.hour + dt_local.minute / 60.0
                if dt_local.date() > record.date:
                    fl += 24.0
                return fl

            total_overtime = 0.0

            # Xử lý register.overtime
            for r in ot_regs:
                r_start = r.start_time
                r_end = r.end_time
                if r_end == 0:
                    r_end = 24
                if r.start_date != r.end_date and r_start > r_end:
                    if r.start_date == record.date:
                        total_overtime += abs(24 - r_start)
                    elif r.end_date == record.date:
                        total_overtime += abs(r_end)
                else:
                    total_overtime += abs(r_end - r_start)

            # Xử lý overtime.rel theo logic gốc (phức tạp)
            for x in overtime_rels:
                if not record.shift:
                    continue

                # helper lấy giờ ca
                if not record.shift.shift_ot:
                    shift_start = (record.shift.start + relativedelta(hours=7)).hour + \
                                  (record.shift.start + relativedelta(hours=7)).minute / 60.0
                    shift_end = (record.shift.end_shift + relativedelta(hours=7)).hour + \
                                (record.shift.end_shift + relativedelta(hours=7)).minute / 60.0

                    ot_start = x.start_time
                    ot_end = x.end_time
                    if ot_end == 0:
                        ot_end = 24

                    # trường hợp OT trước ca
                    if ot_end <= shift_start:
                        gap = shift_start - ot_end
                        if gap >= 1:
                            total_overtime += ot_end - ot_start
                        else:
                            if record.check_in:
                                check_in_time = _dt_to_float_local(record.check_in)
                                actual_start = max(ot_start, check_in_time)
                                actual_end = ot_end
                                if record.check_out:
                                    check_out_time = _dt_to_float_local(record.check_out)
                                    actual_end = min(actual_end, check_out_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                    # trường hợp OT sau ca
                    elif shift_end <= ot_start:
                        gap = ot_start - shift_end
                        if gap >= 1:
                            total_overtime += ot_end - ot_start
                        else:
                            if record.check_out:
                                check_out_time = _dt_to_float_local(record.check_out)
                                actual_start = ot_start
                                actual_end = min(ot_end, check_out_time)
                                if record.check_in:
                                    check_in_time = _dt_to_float_local(record.check_in)
                                    actual_start = max(actual_start, check_in_time)
                                if actual_end > actual_start:
                                    total_overtime += actual_end - actual_start

                    # OT chồng ca / trong ca
                    else:
                        # phần trước ca
                        if ot_start < shift_start:
                            actual_start = ot_start
                            if record.check_in:
                                check_in_time = _dt_to_float_local(record.check_in)
                                actual_start = max(actual_start, check_in_time)
                            actual_end = min(ot_end, shift_start)
                            if record.check_out:
                                check_out_time = _dt_to_float_local(record.check_out)
                                actual_end = min(actual_end, check_out_time)
                            if actual_end > actual_start:
                                total_overtime += actual_end - actual_start

                        # phần sau ca
                        if ot_end > shift_end:
                            actual_start = max(ot_start, shift_end)
                            if record.check_in:
                                check_in_time = _dt_to_float_local(record.check_in)
                                actual_start = max(actual_start, check_in_time)
                            actual_end = ot_end
                            if record.check_out:
                                check_out_time = _dt_to_float_local(record.check_out)
                                actual_end = min(actual_end, check_out_time)
                            if actual_end > actual_start:
                                total_overtime += actual_end - actual_start

                        # phần trong ca
                        inside_start = max(ot_start, shift_start)
                        inside_end = min(ot_end, shift_end)
                        if record.check_in:
                            check_in_time = _dt_to_float_local(record.check_in)
                            inside_start = max(inside_start, check_in_time)
                        if record.check_out:
                            check_out_time = _dt_to_float_local(record.check_out)
                            inside_end = min(inside_end, check_out_time)
                        if inside_end > inside_start:
                            total_overtime += inside_end - inside_start
                else:
                    # shift_ot True -> tính theo OT đăng ký + cắt theo check_in/out
                    if record.check_in and record.check_out:
                        check_in_time = _dt_to_float_local(record.check_in)
                        check_out_time = _dt_to_float_local(record.check_out)
                        actual_start = max(x.start_time, check_in_time)
                        ot_end = x.end_time if x.end_time != 0 else 24
                        actual_end = min(ot_end, check_out_time)
                        if actual_end > actual_start:
                            total_overtime += actual_end - actual_start

            # gán kết quả
            if record.shift and record.shift.type_ot == 'nb':
                record.over_time_nb = total_overtime * (record.shift.coefficient or 1.0)
                record.over_time = 0.0
            else:
                # giữ logic nhân đôi cho một số công ty / chủ nhật
                if record.weekday == '6' and record.employee_id.company_id and record.employee_id.company_id.id == 16:
                    record.over_time = total_overtime * 2.0
                else:
                    record.over_time = total_overtime

    @api.depends('date')
    def _compute_month_year(self):
        for r in self:
            if r.date:
                r.month = r.date.month
                r.year = r.date.year
            else:
                r.month = None
                r.year = None

    # tạo bản ghi tháng trước -> logic giữ nguyên (giữ như tiện ích admin)
    def update_attendance_data_v2(self):
        # STEP 1 — Lấy danh sách nhân viên
        self.env.cr.execute("""
            SELECT id 
            FROM hr_employee 
            WHERE id != 1
        """)
        employee_ids = [row[0] for row in self.env.cr.fetchall()]

        # STEP 2 — Tính khoảng thời gian
        now = datetime.now()
        start_date = now.replace(day=1).date() - relativedelta(months=1)
        end_date = (start_date + relativedelta(months=2)) - timedelta(days=1)

        # STEP 3 — Lấy bản ghi đã tồn tại để bỏ qua
        self.env.cr.execute("""
            SELECT employee_id, date 
            FROM employee_attendance_v2
            WHERE date BETWEEN %s AND %s
        """, (start_date, end_date))

        existing = {(row[0], row[1]) for row in self.env.cr.fetchall()}

        # STEP 4 — Tạo list insert
        values = []
        cur = start_date
        while cur <= end_date:
            for emp_id in employee_ids:
                if (emp_id, cur) not in existing:
                    values.append(f"({emp_id}, '{cur}')")
            cur += timedelta(days=1)

        # STEP 5 — Insert bằng batch SQL
        if values:
            batch_size = 5000
            for i in range(0, len(values), batch_size):
                batch = values[i:i + batch_size]
                sql = """
                    INSERT INTO employee_attendance_v2 (employee_id, date)
                    VALUES %s
                """ % ",".join(batch)
                self.env.cr.execute(sql)

        # STEP 6 — RECOMPUTE cho từng employee từng ngày
        Attendance = self.env['employee.attendance.v2'].sudo()
        cur = start_date
        while cur <= end_date:
            for emp_id in employee_ids:
                emp = self.env['hr.employee'].browse(emp_id)
                Attendance.recompute_for_employee(emp, cur, cur)
            cur += timedelta(days=1)

    @api.depends('date', 'employee_id')
    def _compute_shift_employee(self):
        for r in self:
            r.shift = None
            if not r.date or not r.employee_id:
                continue

            # tìm register.shift.rel trước (ưu tiên)
            shift_rel = self.env['register.shift.rel'].sudo().search([
                ('register_shift.employee_id', '=', r.employee_id.id),
                ('date', '=', r.date)
            ], limit=1)

            if shift_rel:
                # nếu shift_rel là record liên kết -> lấy shift
                # shift_rel có thể là register.shift.rel hoặc register.work; logic cũ khác nhau, giữ nguyên
                if hasattr(shift_rel, 'shift'):
                    r.shift = shift_rel.shift.id if shift_rel.shift else None
                else:
                    # fallback
                    r.shift = None
                continue

            # fallback: tìm trong register.work
            shift_re = self.env['register.work'].sudo().search([
                ('start_date', '<=', r.date),
                ('end_date', '>=', r.date),
                ('employee_id', 'in', [r.employee_id.id])
            ], limit=1)
            if shift_re and hasattr(shift_re, 'shift'):
                r.shift = shift_re.shift.id if shift_re.shift else None
            elif r.employee_id.shift:
                r.shift = r.employee_id.shift.id

    @api.depends('shift')
    def _compute_time_in_out(self):
        for r in self:
            r.time_check_in = None
            r.time_check_out = None
            if not r.shift:
                continue

            # base times
            time_ci = (r.shift.start + timedelta(hours=7)).time()
            time_co = (r.shift.end_shift + timedelta(hours=7)).time()
            dt_date = r.date
            check_time_ci = datetime.combine(dt_date, time_ci)
            check_time_co = datetime.combine(dt_date, time_co)

            # theo logic gốc: earliest, latest_out
            time_check_in = check_time_ci - timedelta(hours=7, minutes=(r.shift.earliest or 0))
            time_check_out = check_time_co - timedelta(hours=7) + timedelta(minutes=(r.shift.latest_out or 0))  # tương đương logic gốc

            # xử lý night shift: nếu check_in & check_out cùng ngày (sau +7) -> check_out +1 ngày
            if getattr(r.shift, 'night', False):
                if (time_check_in + timedelta(hours=7)).date() == (time_check_out + timedelta(hours=7)).date():
                    time_check_out += timedelta(days=1)

            # nếu có overtime/register.overtime ảnh hưởng, điều chỉnh
            ot_regs = self.env['register.overtime'].sudo().search([('employee_id', '=', r.employee_id.id),
                                                                  ('start_date', '<=', r.date),
                                                                  ('end_date', '>=', r.date)])
            ot_rel_update = self.env['overtime.rel'].sudo().search([('date', '=', r.date),
                                                                   ('overtime_id.status', '=', 'done')])
            ot_rel_update = ot_rel_update.filtered(lambda x: (x.overtime_id.employee_id and x.overtime_id.employee_id.id == r.employee_id.id)
                                                   or (x.overtime_id.employee_ids and r.employee_id.id in x.overtime_id.employee_ids.ids))

            def _apply_shift_adjust(start, end, base_ci, base_co):
                s = int(start)
                e = int(end)
                # nếu end == start_hour + 7 -> adjust time_check_in / out
                if e == (r.shift.start.hour + 7):
                    return base_ci - timedelta(hours=(e - s))
                if s == (r.shift.end_shift.hour + 7):
                    return base_co + timedelta(hours=(e - s))
                return base_ci, base_co

            # adjust theo register.overtime
            if ot_regs:
                for ot in ot_regs:
                    start = int(ot.start_time)
                    end = int(ot.end_time)
                    if end == r.shift.start.hour + 7:
                        time_check_in = time_check_in - timedelta(hours=end - start)
                    if start == r.shift.end_shift.hour + 7:
                        time_check_out = time_check_out + timedelta(hours=end - start)

            if ot_rel_update:
                for ot in ot_rel_update:
                    start = int(ot.start_time)
                    end = int(ot.end_time)
                    if end == r.shift.start.hour + 7:
                        time_check_in = time_check_in - timedelta(hours=end - start)
                    if start == r.shift.end_shift.hour + 7:
                        time_check_out = time_check_out + timedelta(hours=end - start)

            r.time_check_in = time_check_in
            r.time_check_out = time_check_out

    @api.depends('shift', 'duration', 'time_check_in', 'time_check_out')
    def _compute_no_in_out(self):
        for r in self:
            r.check_no_in = None
            r.check_no_out = None
            if r.shift and r.duration and r.time_check_in and r.time_check_out:
                duration_half = r.duration / 2.0
                # check_no_in: time_check_in + earliest + latest (giữ logic cũ)
                r.check_no_in = r.time_check_in + timedelta(minutes=(getattr(r.shift, 'earliest', 0) + getattr(r.shift, 'latest', 0)))
                r.check_no_out = r.time_check_out - timedelta(hours=duration_half, minutes=(getattr(r.shift, 'latest_out', 0)))

    @api.depends('employee_id', 'time_check_in', 'time_check_out', 'check_no_in', 'check_no_out', 'date')
    def _compute_check_in_out(self):
        """Lấy check_in/check_out từ master.data.attendance và in_outs (word.slip time type).
           Tối ưu: dùng search_read để chỉ lấy attendance_time (giảm overhead).
        """
        for r in self:
            r.check_in = None
            r.check_out = None
            if not (r.time_check_in and r.time_check_out and r.employee_id and r.date):
                continue

            # Lấy attendance_times trong cửa sổ
            attendance_times = self.env['master.data.attendance'].sudo().search_read(
                [('attendance_time', '>=', r.time_check_in),
                 ('attendance_time', '<=', r.time_check_out),
                 ('employee_id', '=', r.employee_id.id)],
                ['attendance_time'],
                order='attendance_time ASC'
            )
            times = [a['attendance_time'] for a in attendance_times if a.get('attendance_time')]

            # phân tách check_in (<= check_no_in) và check_out (>= check_no_out)
            ci_list = [t for t in times if r.check_no_in and t <= r.check_no_in]
            co_list = [t for t in times if r.check_no_out and t >= r.check_no_out]

            r.check_in = ci_list[0] if ci_list else None
            r.check_out = co_list[-1] if co_list else None

            # Xử lý in_outs từ word.slip (type.date_and_time = 'time')
            in_outs = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('type.date_and_time', '=', 'time'),
                ('word_slip.status', '=', 'done')
            ])
            in_outs = in_outs.filtered(lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id)
                                               or (x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            for in_out in in_outs:
                # time_to -> ci candidate
                if in_out and getattr(in_out, 'time_to', False):
                    ci = self._convert_time_to_datetime(in_out.time_to, r.date)
                    ci = ci - relativedelta(hours=7)
                    if (not r.check_in) and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci
                    elif r.check_in and r.check_in > ci and r.time_check_in and r.check_no_in and r.time_check_in <= ci <= r.check_no_in:
                        r.check_in = ci

                # time_from -> co candidate
                if in_out and getattr(in_out, 'time_from', False):
                    co = self._convert_time_to_datetime(in_out.time_from, r.date)
                    co = co - relativedelta(hours=7)
                    if (not r.check_out) and r.check_no_out and r.time_check_out and r.check_no_out <= co <= r.time_check_out:
                        r.check_out = co
                    elif r.check_out and r.check_out < co and r.check_no_out and r.time_check_out and r.check_no_out <= co <= r.time_check_out:
                        r.check_out = co

    # helper convert time float/int to datetime (giữ nguyên validate logic)
    @staticmethod
    def _convert_time_to_datetime(input_time, dt_date):
        if not isinstance(input_time, (int, float)):
            # trả về đầu ngày để tránh lỗi
            return datetime.combine(dt_date, time(0, 0, 0))
        hour = int(input_time)
        minute = int((input_time % 1) * 60)
        if 0 <= hour < 24:
            return datetime.combine(dt_date, time(hour, minute, 0))
        # nếu giờ >=24 hoặc invalid, fallback về đầu ngày
        return datetime.combine(dt_date, time(0, 0, 0))

    @api.depends('check_in', 'check_out', 'shift', 'leave', 'compensatory', 'vacation')
    def _compute_attendance(self):
        for r in self:
            r.note = None
            if not r.shift:
                r.note = 'no_shift'
                continue
            if (not r.check_in and not r.check_out) or (r.check_in and r.check_out):
                r.note = None
            elif not r.check_in:
                r.note = 'no_in'
            elif not r.check_out:
                r.note = 'no_out'
            if r.leave > 0 or r.compensatory > 0 or r.vacation > 0:
                r.note = None

    @api.depends('shift', 'date', 'check_in', 'check_out', 'leave', 'compensatory', 'vacation')
    def _compute_minutes_late_early(self):
        for r in self:
            r.minutes_late = 0
            r.minutes_early = 0
            if not r.shift or not r.date:
                continue

            shift_start_time = datetime.combine(r.date, r.shift.start.time()) + timedelta(hours=7)
            shift_end_time = datetime.combine(r.date, r.shift.end_shift.time()) + timedelta(hours=7)

            if r.check_in:
                check_in_time = r.check_in + timedelta(hours=7)
                if check_in_time.time() > shift_start_time.time():
                    minutes = (check_in_time - datetime.combine(check_in_time.date(), shift_start_time.time())).total_seconds() / 60.0
                    r.minutes_late = int(minutes)

            if r.check_out:
                check_out_time = r.check_out + timedelta(hours=7)
                if check_out_time < shift_end_time:
                    hour = shift_end_time.time().hour
                    minute = shift_end_time.time().minute
                    second = shift_end_time.time().second
                    if hour == 0:
                        shift_end_in_hours = 24.0
                    else:
                        shift_end_in_hours = hour + minute / 60.0 + second / 3600.0
                    checkout_hour = check_out_time.hour + check_out_time.minute / 60.0 + check_out_time.second / 3600.0
                    minute_early = (shift_end_in_hours - checkout_hour) * 60.0
                    r.minutes_early = int(minute_early)

            # reset nếu nghỉ
            if r.leave > 0 or r.compensatory > 0 or r.vacation > 0:
                r.minutes_early = 0
                r.minutes_late = 0

            # nếu ca ot hoặc ngày nghỉ lễ cố định
            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]
            if (getattr(r.shift, 'shift_ot', False)) or (getattr(r.shift, 'is_office_hour', False) and (weekday == 6 or (weekday == 5 and week_number % 2 == 1))):
                r.minutes_early = 0
                r.minutes_late = 0

    @api.depends('check_in', 'check_out', 'shift', 'leave', 'compensatory', 'vacation')
    def _compute_work_day(self):
        for r in self:
            r.work_day = 0
            if not r.shift:
                continue

            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]

            free_time = self.env['free.timekeeping'].sudo().search([
                ('employee_id', '=', r.employee_id.id),
                ('state', '=', 'active'),
                ('start_date', '<=', r.date),
                ('end_date', '>=', r.date)
            ], limit=1)

            leave_no_work = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('word_slip.status', '=', 'done'),
                ('word_slip.type.key', '=', "KL"),
            ])
            leave_no_work = leave_no_work.filtered(lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id)
                                                          or (x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            # business rules như cũ
            if getattr(r.shift, 'is_office_hour', False) and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.work_day = 0
            elif getattr(r.shift, 'shift_ot', False):
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
                    if getattr(r.shift, 'half_shift', False):
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

    @api.depends('minutes_late', 'minutes_early')
    def _compute_times_late(self):
        for r in self:
            r.times_late = 0
            if r.minutes_late >= 31:
                r.times_late = 1
            if r.minutes_early >= 31:
                r.times_late += 1

    @api.depends('shift', 'work_day')
    def _compute_actual_work(self):
        for r in self:
            r.actual_work = (r.work_day * getattr(r.shift, 'recent_work', 0)) if r.shift and r.work_day else 0

    @api.depends('note')
    def _compute_forgot_time(self):
        for r in self:
            r.forgot_time = 1 if r.note in ('no_in', 'no_out') else 0

    @api.depends('work_day')
    def _compute_work_eat(self):
        for r in self:
            r.work_eat = 1 if r.work_day >= 1 else 0

    @api.depends('date', 'check_in', 'check_out', 'minutes_late', 'minutes_early', 'work_day', 'public_leave')
    def _compute_color(self):
        today = date.today()
        for r in self:
            r.color = None
            if not r.date or r.date > today:
                continue

            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]

            # tính on_leave tạm bằng cách lấy word.slip date type
            word_slips = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('type.date_and_time', '=', 'date'),
                ('word_slip.status', '=', 'done')
            ])
            word_slips = word_slips.filtered(lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id)
                                                         or (x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))
            on_leave = 0
            if word_slips:
                for slip in word_slips:
                    if slip.start_time == slip.end_time:
                        on_leave += 0.5
                    elif slip.start_time == 'first_half' and slip.end_time == 'second_half':
                        on_leave += 1

            tong_cong = on_leave + r.public_leave + (r.work_day or 0)

            # xác định màu
            if tong_cong >= 1 and (r.minutes_late == 0 and r.minutes_early == 0):
                r.color = 'green'
            else:
                r.color = 'red'

            if getattr(r.shift, 'half_shift', False):
                if tong_cong >= 0.5 and r.minutes_late == 0 and r.minutes_early == 0:
                    r.color = 'green'
                else:
                    r.color = 'red'

            if weekday == 6 or (weekday == 5 and week_number % 2 == 1):
                if tong_cong == 0 or (r.employee_id.company_id and r.employee_id.company_id.calender_work != 'odd'):
                    r.color = None
                elif r.over_time and r.over_time != 0:
                    r.color = 'green' if (r.minutes_late == 0 and r.minutes_early == 0) else 'red'

            if getattr(r.shift, 'is_office_hour', False) and (weekday == 6 or (weekday == 5 and week_number % 2 == 1)):
                r.color = None

            if (r.employee_id.company_id and r.employee_id.company_id.calender_work != 'odd' and (weekday == 6 or weekday == 5)):
                r.color = None

    # ---------- SEND FCM (giữ nguyên logic) ----------
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
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
            response.raise_for_status()
            res_json = response.json()
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
            return res_json
        except Exception as e:
            return {"error": str(e)}

    def noti_miss_work(self):
        self.queue_job_miss_work()

    def queue_job_miss_work(self):
        today = date.today()
        today_str = today.strftime("%d/%m/%y")
        list_record = self.sudo().search([('date', '=', today)])
        list_record = list_record.filtered(lambda x: bool(x.note) and x.note in ('no_in', 'no_out', 'no_shift'))
        for r in list_record:
            token = getattr(r.employee_id.user_id, 'token', False)
            user_id = getattr(r.employee_id.user_id, 'id', False)
            if token and user_id:
                self.send_fcm_notification(
                    title="Sơn Hà HRM",
                    content="Bạn đang thiếu dữ liệu công ngày " + str(today_str) + " vui lòng kiểm tra lại!",
                    token=token,
                    user_id=user_id,
                    type=3,
                    employee_id=r.employee_id.id,
                    application_id=0,
                )

    # ----------------- HELPERS TO RECOMPUTE FROM OUTSIDE -----------------
    def recompute_for_employee(self, employee, date_from=None, date_to=None):
        """Helper: gọi từ model khác (vd word.slip.write/create/unlink) để
           recompute các employee.attendance liên quan.
           - employee: record or id
           - date_from/date_to: optional date range (datetime.date or str)
        """
        if not employee:
            return
        emp_id = employee.id if hasattr(employee, 'id') else int(employee)
        domain = [('employee_id', '=', emp_id)]
        if date_from:
            domain.append(('date', '>=', fields.Date.to_date(date_from)))
        if date_to:
            domain.append(('date', '<=', fields.Date.to_date(date_to)))
        recs = self.search(domain)
        if recs:
            # ghi lại để force recompute store fields
            recs.sudo().write({'date': recs.date})  # ghi lại trường date để kích hoạt recompute store
            # hoặc gọi recompute cụ thể
            recs._compute_check_in_out()
            recs._compute_time_off()
            recs._compute_hours_reinforcement()
            recs._compute_work_day()
            recs._compute_minutes_late_early()
            recs._compute_attendance()
            recs._compute_color()
        return True

    def recompute_for_date_range(self, date_from, date_to):
        """Helper: recompute cho tất cả nhân viên trong khoảng date_from..date_to"""
        if not date_from or not date_to:
            return
        recs = self.search([('date', '>=', fields.Date.to_date(date_from)), ('date', '<=', fields.Date.to_date(date_to))])
        if recs:
            recs.sudo().write({'date': recs.date})
            recs._compute_check_in_out()
            recs._compute_time_off()
            recs._compute_hours_reinforcement()
            recs._compute_work_day()
            recs._compute_minutes_late_early()
            recs._compute_attendance()
            recs._compute_color()
        return True
