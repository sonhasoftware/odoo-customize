# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from datetime import datetime, time, timedelta, date
import logging
import requests
import json
import io
import base64
import calendar
import xlsxwriter


_logger = logging.getLogger(__name__)


class EmployeeAttendanceV2(models.Model):
    _name = 'employee.attendance.v2'
    _description = 'Bảng công chi tiết'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, store=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', store=True, compute="get_department")
    date = fields.Date(string='Ngày', required=True, store=True)
    weekday = fields.Selection([
        ('0', 'Thứ hai'), ('1', 'Thứ ba'), ('2', 'Thứ tư'),
        ('3', 'Thứ năm'), ('4', 'Thứ sáu'), ('5', 'Thứ bảy'),
        ('6', 'Chủ nhật')
    ], string="Thứ", compute="_compute_weekday", store=True)

    check_in = fields.Datetime(string='Giờ vào', compute="_get_check_in_out", store=True)
    check_out = fields.Datetime(string='Giờ ra', compute="_get_check_in_out", store=True)
    duration = fields.Float("Giờ công", compute="_get_duration", store=True)

    shift = fields.Many2one('config.shift', string="Ca làm việc",
                            compute="_get_shift_employee", store=True)
    time_check_in = fields.Datetime("Thời gian phải vào", compute="_get_time_in_out", store=True)
    time_check_out = fields.Datetime("Thời gian phải ra", compute="_get_time_in_out", store=True)
    check_no_in = fields.Datetime("Check không có check_in", compute="_check_no_in_out", store=True)
    check_no_out = fields.Datetime("Check không có check_out", compute="_check_no_in_out", store=True)

    note = fields.Selection([
        ('no_in', "Không có check in"),
        ('no_out', "Không có check out"),
        ('no_shift', "Không có ca làm việc")
    ], string="Ghi chú", compute="_get_attendance", store=True)

    work_day = fields.Float("Ngày công", compute="_get_work_day", store=True)
    minutes_late = fields.Float("Số phút đi muộn", compute="_get_minute_late_early", store=True)
    minutes_early = fields.Float("Số phút về sớm", compute="_get_minute_late_early", store=True)

    month = fields.Integer("Tháng", compute="_get_month_year", store=True)
    year = fields.Integer("Năm", compute="_get_month_year", store=True)

    over_time = fields.Float("Giờ làm thêm", compute="get_hours_reinforcement", store=True)
    over_time_nb = fields.Float("Làm thêm hưởng NB", compute="get_hours_reinforcement", store=True)

    leave = fields.Float("Nghỉ phép", compute="_get_time_off", store=True)
    compensatory = fields.Float("Nghỉ bù", compute="_get_time_off", store=True)
    public_leave = fields.Float("Nghỉ lễ", compute="_get_time_off", store=True)
    vacation = fields.Float("Nghỉ mát", compute="_get_time_off", store=True)
    unpaid_leave = fields.Float("Nghỉ không lương", compute="_get_time_off", store=True)
    paid_leave_slip = fields.Float("Đơn nghỉ có hưởng lương", compute="_get_time_off", store=True)

    c2k3 = fields.Float("Ca 2 kíp 3", compute="get_shift", store=True)
    c3k4 = fields.Float("Ca 3 kíp 4", compute="get_shift", store=True)
    shift_toxic = fields.Float("Ca độc hại", compute="get_shift", store=True)

    work_hc = fields.Float("Công hành chính", compute="get_work_hc_sp", store=True)
    work_sp = fields.Float("Công Sản phẩm", compute="get_work_hc_sp", store=True)

    times_late = fields.Integer("Đi muộn quá 30p", compute="get_times_late", store=True)
    work_calendar = fields.Boolean("Lịch làm việc", compute="get_work_calendar", store=True)

    actual_work = fields.Float("Công thực tế theo ca", compute="_get_actual_work", store=True)

    forgot_time = fields.Integer("Quên CI/CO", compute="_get_forgot_time", store=True)
    work_eat = fields.Integer("Công ăn", compute="_get_work_eat", store=True)

    color = fields.Selection([('red', 'Red'), ('green', 'Green')], string="Màu", compute="_compute_color")
    key = fields.Char("Ký hiệu ca", related="shift.key")

    sunday_work = fields.Float(string="Giờ làm chủ nhật", compute="_get_sunday_work", store=True)
    normal_sunday_work = fields.Float(string="Làm bình thường ngày chủ nhật", compute="_get_sunday_work", store=True)
    ot_sunday_work = fields.Float(string="Làm thêm ngày chủ nhật", compute="get_hours_reinforcement", store=True)

    filial_leave = fields.Float(string="Nghỉ bố mẹ mất", store=True)
    wedding_leave = fields.Float(string="Nghỉ cưới", store=True)
    regime_leave = fields.Float(string="Nghỉ chế độ", store=True)


    LOCAL_TZ_OFFSET = timedelta(hours=7)
    CHECK_WINDOW_HOURS = 1
    MAX_OT_SHIFT_GAP_HOURS = 1

    def _get_actual_attendance_interval_local(self, record):
        """Return the actual CI/CO anchors after considering contiguous overtime."""
        shift_start, shift_end = self._get_shift_interval_local(record)
        if not shift_start or not shift_end:
            return None, None

        actual_start = shift_start
        actual_end = shift_end
        for line in self._get_owned_overtime_lines(record):
            ot_start, ot_end = self._get_overtime_line_interval_local(line)
            if not ot_start or not ot_end:
                continue
            if ot_end <= shift_start:
                actual_start = min(actual_start, ot_start)
            elif ot_start >= shift_end:
                actual_end = max(actual_end, ot_end)
            elif record.shift.shift_ot:
                actual_start = min(actual_start, ot_start)
                actual_end = max(actual_end, ot_end)

        return actual_start, actual_end

    def _get_preferred_attendance_windows_local(self, record):
        actual_start, actual_end = self._get_actual_attendance_interval_local(record)
        if not actual_start or not actual_end:
            return {}

        split_local = actual_start + (actual_end - actual_start) / 2
        one_hour = timedelta(hours=self.CHECK_WINDOW_HOURS)
        return {
            'check_in': (actual_start - one_hour, min(actual_start + one_hour, split_local)),
            'check_out': (max(actual_end - one_hour, split_local), actual_end + one_hour),
            'split': split_local,
            'actual_start': actual_start,
            'actual_end': actual_end,
        }

    def _get_attendance_priority_windows_utc(self, record):
        """Return preferred and fallback CI/CO windows for raw attendance matching."""
        preferred = self._get_preferred_attendance_windows_local(record)
        if not preferred:
            return {}

        actual_start = preferred['actual_start']
        actual_end = preferred['actual_end']
        split_local = preferred['split']

        check_in_fallback_start = datetime.combine(actual_start.date(), time.min)
        check_out_fallback_end = datetime.combine(actual_end.date(), time.max)

        neighbor_records = self.sudo().search([
            ('employee_id', '=', record.employee_id.id),
            ('date', '>=', record.date - timedelta(days=1)),
            ('date', '<=', record.date + timedelta(days=1)),
        ])
        for neighbor in neighbor_records:
            if neighbor.id == record.id:
                continue
            neighbor_preferred = self._get_preferred_attendance_windows_local(neighbor)
            neighbor_check_in = neighbor_preferred.get('check_in')
            neighbor_check_out = neighbor_preferred.get('check_out')

            if neighbor_check_out:
                neighbor_co_start, neighbor_co_end = neighbor_check_out
                if neighbor_co_end.date() == actual_start.date() and neighbor_co_end <= split_local:
                    check_in_fallback_start = max(check_in_fallback_start, neighbor_co_end)
                elif neighbor_co_start.date() == actual_start.date() and neighbor_co_start < split_local:
                    check_in_fallback_start = max(check_in_fallback_start, min(neighbor_co_end, split_local))

            if neighbor_check_in:
                neighbor_ci_start, neighbor_ci_end = neighbor_check_in
                if neighbor_ci_start.date() == actual_end.date() and neighbor_ci_start >= split_local:
                    check_out_fallback_end = min(check_out_fallback_end, neighbor_ci_start)
                elif neighbor_ci_end.date() == actual_end.date() and neighbor_ci_end > split_local:
                    check_out_fallback_end = min(check_out_fallback_end, max(neighbor_ci_start, split_local))

        return {
            'check_in_preferred': (self._to_utc_datetime(preferred['check_in'][0]),
                                   self._to_utc_datetime(preferred['check_in'][1])),
            'check_in_fallback': (self._to_utc_datetime(check_in_fallback_start),
                                  self._to_utc_datetime(split_local)),
            'check_out_preferred': (self._to_utc_datetime(preferred['check_out'][0]),
                                    self._to_utc_datetime(preferred['check_out'][1])),
            'check_out_fallback': (self._to_utc_datetime(split_local),
                                   self._to_utc_datetime(check_out_fallback_end)),
        }

    def _filter_attendance_values_in_window(self, attendance_values, window):
        start, end = window
        if not start or not end or end < start:
            return []
        return [value for value in attendance_values if start <= value <= end]

    def _to_local_datetime(self, dt):
        return dt + self.LOCAL_TZ_OFFSET if dt else None

    def _to_utc_datetime(self, dt):
        return dt - self.LOCAL_TZ_OFFSET if dt else None

    def _float_hour_to_local_datetime(self, base_date, hour_float):
        hour_float = hour_float or 0
        if hour_float >= 24:
            return datetime.combine(base_date, time(0, 0)) + timedelta(days=1)
        hours = int(hour_float)
        minutes = int(round((hour_float - hours) * 60))
        if minutes >= 60:
            hours += minutes // 60
            minutes = minutes % 60
        if hours >= 24:
            return datetime.combine(base_date, time(0, 0)) + timedelta(days=1, hours=hours - 24, minutes=minutes)
        return datetime.combine(base_date, time(hours, minutes))

    def _get_shift_interval_local(self, record):
        if not record.shift or not record.shift.start or not record.shift.end_shift or not record.date:
            return None, None
        start_time = self._to_local_datetime(record.shift.start).time()
        end_time = self._to_local_datetime(record.shift.end_shift).time()
        shift_start = datetime.combine(record.date, start_time)
        shift_end = datetime.combine(record.date, end_time)
        if shift_end <= shift_start:
            shift_end += timedelta(days=1)
        return shift_start, shift_end

    def _is_shift_overnight(self, record):
        shift_start, shift_end = self._get_shift_interval_local(record)
        return bool(shift_start and shift_end and shift_end.date() > shift_start.date())

    def _get_shift_rest_interval_local(self, record):
        if (
                not record.shift
                or not record.shift.from_rest
                or not record.shift.to_rest
                or not record.date
                or self._is_shift_overnight(record)
        ):
            return None, None

        shift_start, shift_end = self._get_shift_interval_local(record)
        if not shift_start or not shift_end:
            return None, None

        rest_start_time = self._to_local_datetime(record.shift.from_rest).time()
        rest_end_time = self._to_local_datetime(record.shift.to_rest).time()
        rest_start = datetime.combine(record.date, rest_start_time)
        rest_end = datetime.combine(record.date, rest_end_time)
        if rest_end <= rest_start:
            rest_end += timedelta(days=1)

        if rest_start <= shift_start or rest_end >= shift_end:
            return None, None
        return rest_start, rest_end

    def _get_shift_work_intervals_local(self, record):
        shift_start, shift_end = self._get_shift_interval_local(record)
        if not shift_start or not shift_end:
            return []

        rest_start, rest_end = self._get_shift_rest_interval_local(record)
        if not rest_start or not rest_end:
            return [(shift_start, shift_end)]

        return [(shift_start, rest_start), (rest_end, shift_end)]

    def _is_overtime_inside_shift_rest(self, record, line):
        if not record or not line or record.shift.shift_ot:
            return False
        ot_start, ot_end = self._get_overtime_line_interval_local(line)
        rest_start, rest_end = self._get_shift_rest_interval_local(record)
        return bool(ot_start and ot_end and rest_start and rest_end and ot_start >= rest_start and ot_end <= rest_end)

    def _get_overtime_work_overlap_hours(self, record, line):
        ot_start, ot_end = self._get_overtime_line_interval_local(line)
        if not ot_start or not ot_end:
            return 0

        total = 0
        for work_start, work_end in self._get_shift_work_intervals_local(record):
            overlap_start, overlap_end = self._intersect_interval(ot_start, ot_end, work_start, work_end)
            total += self._duration_hours(overlap_start, overlap_end)
        return total

    def _get_shift_split_utc(self, record):
        shift_start, shift_end = self._get_shift_interval_local(record)
        if not shift_start or not shift_end:
            return None
        split_local = shift_start + (shift_end - shift_start) / 2
        return self._to_utc_datetime(split_local)

    def _get_overtime_line_interval_local(self, line):
        if not line or not line.date:
            return None, None
        start = self._float_hour_to_local_datetime(line.date, line.start_time)
        end = self._float_hour_to_local_datetime(line.date, line.end_time)
        if end <= start:
            end += timedelta(days=1)
        return start, end

    def _intersect_interval(self, start_a, end_a, start_b, end_b):
        start = max(start_a, start_b)
        end = min(end_a, end_b)
        if end <= start:
            return None, None
        return start, end

    def _duration_hours(self, start, end):
        if not start or not end or end <= start:
            return 0
        return (end - start).total_seconds() / 3600

    def _is_overtime_line_employee(self, line, employee):
        overtime = line.overtime_id
        return bool(
            (overtime.employee_id and overtime.employee_id.id == employee.id) or
            (overtime.employee_ids and employee.id in overtime.employee_ids.ids)
        )

    def _get_overtime_candidates(self, employee, date_from, date_to):
        lines = self.env['overtime.rel'].sudo().search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            '|',
            ('overtime_id.status', '=', 'done'),
            ('overtime_id.status_lv2', '=', 'done'),
        ])
        return lines.filtered(lambda line: self._is_overtime_line_employee(line, employee))

    def _get_overtime_owner_record(self, line, employee):
        ot_start, ot_end = self._get_overtime_line_interval_local(line)
        if not ot_start or not ot_end:
            return self.env['employee.attendance.v2']
        records = self.sudo().search([
            ('employee_id', '=', employee.id),
            ('date', '>=', line.date - timedelta(days=1)),
            ('date', '<=', line.date + timedelta(days=1)),
        ])
        best_record = self.env['employee.attendance.v2']
        best_key = None
        for attendance in records:
            shift_start, shift_end = self._get_shift_interval_local(attendance)
            if not shift_start or not shift_end:
                continue
            overlap_start, overlap_end = self._intersect_interval(ot_start, ot_end, shift_start, shift_end)
            overlap_hours = self._duration_hours(overlap_start, overlap_end)
            if attendance.shift.shift_ot and overlap_hours:
                key = (0, -overlap_hours, abs((ot_start - shift_start).total_seconds()))
            elif not attendance.shift.shift_ot:
                if self._is_overtime_inside_shift_rest(attendance, line):
                    key = (0, 0, abs((ot_start - shift_start).total_seconds()))
                elif overlap_hours:
                    key = (0, -overlap_hours, abs((ot_start - shift_start).total_seconds()))
                elif ot_end <= shift_start:
                    gap_hours = self._duration_hours(ot_end, shift_start)
                    priority = 1 if gap_hours <= self.MAX_OT_SHIFT_GAP_HOURS else 2 if line.date == attendance.date else 3
                    key = (priority, gap_hours, 0)
                elif ot_start >= shift_end:
                    gap_hours = self._duration_hours(shift_end, ot_start)
                    priority = 1 if gap_hours <= self.MAX_OT_SHIFT_GAP_HOURS else 2 if ot_start.date() == shift_end.date() else 3
                    key = (priority, gap_hours, 0)
                else:
                    continue
            else:
                continue
            if best_key is None or key < best_key:
                best_key = key
                best_record = attendance
        return best_record

    def _get_owned_overtime_lines(self, record):
        if not record.employee_id or not record.date or not record.shift:
            return self.env['overtime.rel']
        shift_start, shift_end = self._get_shift_interval_local(record)
        if not shift_start or not shift_end:
            return self.env['overtime.rel']
        candidates = self._get_overtime_candidates(
            record.employee_id,
            shift_start.date() - timedelta(days=1),
            shift_end.date() + timedelta(days=1),
        )
        return candidates.filtered(lambda line: self._get_overtime_owner_record(line, record.employee_id).id == record.id)

    def _get_actual_overtime_hours_for_line(self, record, line):
        if not record.check_in or not record.check_out:
            return 0
        ot_start, ot_end = self._get_overtime_line_interval_local(line)
        actual_start = self._to_local_datetime(record.check_in)
        actual_end = self._to_local_datetime(record.check_out)
        work_start, work_end = self._intersect_interval(ot_start, ot_end, actual_start, actual_end)
        if not work_start or not work_end:
            return 0
        if record.shift.shift_ot:
            return self._duration_hours(work_start, work_end)

        total = self._duration_hours(work_start, work_end)
        for shift_work_start, shift_work_end in self._get_shift_work_intervals_local(record):
            inside_start, inside_end = self._intersect_interval(work_start, work_end, shift_work_start, shift_work_end)
            total -= self._duration_hours(inside_start, inside_end)
        return max(total, 0)

    def _get_actual_compensatory_hours_for_overtime(self, overtime, employee):
        total = 0
        for line in overtime.date:
            if not line.date or not self._is_overtime_line_employee(line, employee):
                continue
            owner = self._get_overtime_owner_record(line, employee)
            if owner:
                total += self._get_actual_overtime_hours_for_line(owner, line) * (line.coefficient or 1)
        return total

    @api.depends('employee_id', 'check_in', 'check_out', 'date')
    def _get_sunday_work(self):
        for r in self:
            r.sunday_work = 0
            r.normal_sunday_work = 0
            if r.weekday == '6':
                word_slip = self.env['word.slip'].sudo().search([('from_date', '<=', r.date),
                                                                 ('to_date', '>=', r.date),
                                                                 ('word_slip.status', '=', 'done')])
                word_slips = word_slip.filtered(
                    lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (
                            x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

                for slip in word_slips:
                    if slip.word_slip.type.sunday_count == 'haft' and slip.start_time == slip.end_time and (r.check_in or r.check_out):
                        if r.shift.start and r.shift.end_shift:
                            time_ci = (r.shift.start + timedelta(hours=7)).time()
                            time_co = (r.shift.end_shift + timedelta(hours=7)).time()
                            date = r.date
                            check_time_ci = datetime.combine(date, time_ci)
                            check_time_co = datetime.combine(date, time_co)

                            shift_work = abs((check_time_co - check_time_ci).total_seconds() / 3600)

                            r.sunday_work += shift_work/2
                            if not r.shift.shift_ot:
                                r.normal_sunday_work += shift_work/2
                    elif slip.word_slip.type.sunday_count == 'full' and r.check_in and r.check_out:
                        sun_work = abs((r.check_out - r.check_in).total_seconds() / 3600)
                        r.sunday_work += sun_work
                        if not r.shift.shift_ot:
                            r.normal_sunday_work += sun_work
                if not word_slips:
                    if r.check_in and r.check_out:
                        sun_work = abs((r.check_out - r.check_in).total_seconds() / 3600)
                        r.sunday_work += sun_work
                        if not r.shift.shift_ot:
                            r.normal_sunday_work += sun_work

    @api.depends('employee_id')
    def get_department(self):
        for r in self:
            if r.employee_id and r.employee_id.department_id:
                r.department_id = r.employee_id.department_id.id
            else:
                r.department_id = None

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
            r.unpaid_leave = 0
            r.paid_leave_slip = 0
            r.regime_leave = 0
            r.filial_leave = 0
            r.wedding_leave = 0

            if not r.employee_id or not r.date:
                continue

            # Tìm tất cả các word.slip liên quan
            word_slips = self.env['word.slip'].sudo().search([
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('word_slip.status', '=', 'done')
            ])

            word_slips = word_slips.filtered(
                lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == r.employee_id.id) or (
                            x.word_slip.employee_ids and r.employee_id.id in x.word_slip.employee_ids.ids))

            # Xử lý word.slip
            for slip in word_slips:
                type_name = slip.word_slip.type.name.lower()
                key = slip.word_slip.type.key.lower()
                if type_name == "nghỉ phép":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.leave = 1
                        else:
                            r.leave += 0.5
                    else:
                        r.leave = 0
                elif type_name == "nghỉ bù":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.compensatory = 1
                        else:
                            r.compensatory += 0.5
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
                elif key == "kl":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.unpaid_leave = 1
                        else:
                            r.unpaid_leave = 0.5
                    else:
                        r.unpaid_leave = 0
                elif key == "tkn":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.paid_leave_slip = 1
                        else:
                            r.paid_leave_slip = 0.5
                    else:
                        r.paid_leave_slip = 0
                elif key == "cd":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.regime_leave = 1
                        else:
                            r.regime_leave = 0.5
                elif key == "nc":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.wedding_leave = 1
                        else:
                            r.wedding_leave = 0.5
                elif key == "bmm":
                    if slip.start_time and slip.end_time:
                        if slip.start_time != slip.end_time:
                            r.filial_leave = 1
                        else:
                            r.filial_leave = 0.5

            # Kiểm tra public leave
            if all_public_leaves.filtered(
                    lambda leave: leave.date_from.date() <= r.date <= leave.date_to.date()):
                if r.work_day == 0 and r.over_time == 0 and r.over_time_nb == 0 and r.employee_id.onboard < r.date:
                    r.public_leave = 1

    @api.depends('employee_id', 'date', 'check_in', 'check_out', 'shift')
    def get_hours_reinforcement(self):
        for record in self:
            record.over_time = 0
            record.over_time_nb = 0
            if not record.employee_id or not record.shift:
                continue

            record.ot_sunday_work = 0
            total_overtime = 0
            for line in self._get_owned_overtime_lines(record):
                total_overtime += self._get_actual_overtime_hours_for_line(record, line)

            if record.shift.type_ot == 'nb':
                record.over_time_nb = total_overtime * (record.shift.coefficient or 1)
                record.over_time = 0
            else:
                if record.weekday == '6':
                    record.ot_sunday_work = total_overtime
                if record.weekday == '6' and record.employee_id.company_id.id == 16:
                    record.over_time = total_overtime * 2
                else:
                    record.over_time = total_overtime
                if record.employee_id.department_id.produce_department and record.weekday != '6':
                    if total_overtime < 1:
                        record.over_time = 0

    @api.depends('date')
    def _get_month_year(self):
        for r in self:
            if r.date:
                r.month = r.date.month
                r.year = r.date.year
            else:
                r.month = None
                r.year = None

    # tạo ra bản ghi cho từng nhân viên trong các ngày của tháng

    def update_attendance_data_v2(self):
        period_key = datetime.now().strftime('%Y-%m')
        self.with_delay(
            identity_key=f'employee_attendance_v2_create_data_attendance_{period_key}',
            description=_('Tạo dữ liệu bảng công chi tiết V2 %s') % period_key,
        ).create_data_attendance()

    def update_new_emp_attendance_data_v2(self):
        self.with_delay().create_data_attendance_new_emp()

    def _split_employee_batches(self, employee_ids, batch_size):
        batch_size = batch_size or 50
        for index in range(0, len(employee_ids), batch_size):
            yield employee_ids[index:index + batch_size]

    def create_data_attendance(self, recompute_batch_size=50):
        # Tránh 2 queue job cùng tạo dữ liệu tháng chạy song song làm trùng bản ghi và nghẽn DB.
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(20260605, 1001)")
        if not self.env.cr.fetchone()[0]:
            _logger.info('Skip create_data_attendance because another attendance V2 job is running.')
            return

        now = datetime.now()
        start_date = now.replace(day=1).date() - relativedelta(months=1)
        current_month_start = now.replace(day=1).date()
        end_date = (start_date + relativedelta(months=2)) - timedelta(days=1)

        # Tạo bản ghi thiếu bằng SQL set-based giống create_data_attendance_new_emp:
        # PostgreSQL sinh toàn bộ cặp employee/date, tự loại cặp đã tồn tại và insert một lần.
        query = """
            CREATE TEMP TABLE temp_employee_attendance_v2_dates ON COMMIT DROP AS
                SELECT
                    e.id AS employee_id,
                    gs::date AS date
                FROM hr_employee e
                CROSS JOIN generate_series(
                    %s::date,
                    %s::date,
                    interval '1 day'
                ) AS gs
                WHERE e.id != 1;

            CREATE TEMP TABLE temp_existing_employee_attendance_v2_dates ON COMMIT DROP AS
                SELECT employee_id, date
                FROM employee_attendance_v2
                WHERE date BETWEEN %s AND %s;

            CREATE TEMP TABLE temp_missing_employee_attendance_v2_dates ON COMMIT DROP AS
                SELECT
                    ted.employee_id,
                    ted.date
                FROM temp_employee_attendance_v2_dates ted
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM temp_existing_employee_attendance_v2_dates tad
                    WHERE tad.employee_id = ted.employee_id
                    AND tad.date = ted.date
                );

            INSERT INTO employee_attendance_v2 (employee_id, date)
                SELECT
                    t.employee_id,
                    t.date
                FROM temp_missing_employee_attendance_v2_dates t;

            SELECT COUNT(*) AS inserted_count
            FROM temp_missing_employee_attendance_v2_dates;
        """
        self.env.cr.execute(query, (start_date, end_date, start_date, end_date))
        inserted_count = self.env.cr.fetchone()[0]

        # Chỉ recompute tháng hiện tại để giảm khối lượng xử lý từ ~2 tháng xuống còn 1 tháng.
        # Mỗi batch là một queue job riêng để tránh một job lớn xử lý >2.000 nhân viên bị treo worker.
        self.env.cr.execute("""
            SELECT DISTINCT employee_id
            FROM employee_attendance_v2
            WHERE date BETWEEN %s AND %s
            ORDER BY employee_id
        """, (current_month_start, end_date))
        employee_ids = [row[0] for row in self.env.cr.fetchall()]

        _logger.info(
            'Created %s missing employee_attendance_v2 rows for %s -> %s. Enqueue recompute %s employees for %s -> %s.',
            inserted_count, start_date, end_date, len(employee_ids), current_month_start, end_date,
        )

        date_from = current_month_start.isoformat()
        date_to = end_date.isoformat()
        for batch_number, batch_employee_ids in enumerate(
                self._split_employee_batches(employee_ids, recompute_batch_size), start=1):
            first_emp = batch_employee_ids[0]
            last_emp = batch_employee_ids[-1]
            self.with_delay(
                identity_key=(
                    'employee_attendance_v2_recompute_%s_%s_%s_%s' %
                    (date_from, date_to, first_emp, last_emp)
                ),
                description=_('Recompute bảng công V2 %s - batch %s') % (date_from, batch_number),
            ).create_data_attendance_recompute_batch(batch_employee_ids, date_from, date_to)

    def create_data_attendance_recompute_batch(self, employee_ids, date_from, date_to):
        if not employee_ids:
            return
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        attendance = self.env['employee.attendance.v2'].sudo()
        _logger.info(
            'Start recompute employee_attendance_v2 for %s employees from %s to %s.',
            len(employee_ids), date_from, date_to,
        )
        for emp_id in employee_ids:
            attendance.recompute_for_employee(emp_id, date_from, date_to)
        _logger.info(
            'Done recompute employee_attendance_v2 for %s employees from %s to %s.',
            len(employee_ids), date_from, date_to,
        )

    def create_data_attendance_new_emp(self):
        now = datetime.now().replace(day=1)
        start_date = now.replace(day=1).date() - relativedelta(months=1)
        end_date = (start_date + relativedelta(months=2)) - timedelta(days=1)
        query = """
            CREATE TEMP TABLE temp_employee_dates ON COMMIT DROP AS
                SELECT
                    e.id AS employee_id,
                    gs::date AS date
                FROM hr_employee e
                CROSS JOIN generate_series(
                    %s,
                    %s,
                    interval '1 day'
                ) AS gs
                WHERE e.id != 1
                AND onboard >= %s;
            
            CREATE TEMP TABLE temp_attendance_dates ON COMMIT DROP AS
                SELECT employee_id, date 
                FROM employee_attendance_v2
                WHERE date BETWEEN %s AND %s;
            
            CREATE TEMP TABLE temp_missing_dates ON COMMIT DROP AS
                SELECT
                    ted.employee_id,
                    ted.date
                FROM temp_employee_dates ted
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM temp_attendance_dates tad
                    WHERE tad.employee_id = ted.employee_id
                    AND tad.date = ted.date
                );
                
            INSERT INTO employee_attendance_v2 (employee_id, date)
                SELECT
                    t.employee_id,
                    t.date
                FROM temp_missing_dates t;
                
            SELECT
                employee_id,
                MIN(date) AS start_date,
                MAX(date) AS end_date
            FROM temp_missing_dates
            GROUP BY employee_id;
        """
        self.env.cr.execute(query, (start_date, end_date, now.date(), start_date, end_date))
        rows = self.env.cr.dictfetchall()
        if rows:
            attendance = self.env['employee.attendance.v2'].sudo()
            for r in rows:
                attendance.recompute_for_employee(r["employee_id"], r["start_date"], r["end_date"])

    # lấy thông tin ca của nhân viên để điền vào trường ca
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

    # Lấy thông tin giờ phải check-in và giờ check-out của nhân viên
    @api.depends('shift', 'employee_id', 'date')
    def _get_time_in_out(self):
        for r in self:
            r.time_check_in = None
            r.time_check_out = None
            if not r.shift or not r.shift.start or not r.shift.end_shift or not r.date:
                continue

            shift_start, shift_end = self._get_shift_interval_local(r)
            if not shift_start or not shift_end:
                continue

            window_start = shift_start - timedelta(hours=self.CHECK_WINDOW_HOURS)
            window_end = shift_end + timedelta(hours=self.CHECK_WINDOW_HOURS)

            for line in self._get_owned_overtime_lines(r):
                ot_start, ot_end = self._get_overtime_line_interval_local(line)
                if not ot_start or not ot_end:
                    continue
                if ot_end <= shift_start:
                    window_start = min(window_start, ot_start - timedelta(hours=self.CHECK_WINDOW_HOURS))
                elif ot_start >= shift_end:
                    window_end = max(window_end, ot_end + timedelta(hours=self.CHECK_WINDOW_HOURS))
                elif r.shift.shift_ot:
                    window_start = min(window_start, ot_start - timedelta(hours=self.CHECK_WINDOW_HOURS))
                    window_end = max(window_end, ot_end + timedelta(hours=self.CHECK_WINDOW_HOURS))

            r.time_check_in = self._to_utc_datetime(window_start)
            r.time_check_out = self._to_utc_datetime(window_end)

    # Lấy ra thông tin số giờ cần có mặt theo ca
    @api.depends('shift')
    def _get_duration(self):
        for r in self:
            if r.shift and r.shift.start and r.shift.end_shift:
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

    # Lấy giờ mốc để tách giờ check-in và giờ check-out của nhân viên
    @api.depends('shift', 'duration', 'time_check_in', 'time_check_out', 'employee_id')
    def _check_no_in_out(self):
        for r in self:
            r.check_no_in = None
            r.check_no_out = None
            split_utc = self._get_shift_split_utc(r)
            if split_utc:
                r.check_no_in = split_utc
                r.check_no_out = split_utc

    def _float_time_to_local_datetime(self, base_date, hour_float):
        if base_date is None or hour_float is None:
            return None
        if not isinstance(hour_float, (int, float)) or hour_float < 0:
            raise ValueError(f"Invalid time value: {hour_float}")

        hour = int(hour_float)
        minute = int(round((hour_float % 1) * 60))
        if minute >= 60:
            hour += minute // 60
            minute = minute % 60
        return datetime.combine(base_date, time(0, 0, 0)) + timedelta(hours=hour, minutes=minute)

    def _get_time_word_slip_pairs_utc(self, word_slip):
        if not word_slip.from_date or not word_slip.to_date:
            return []

        pairs = []
        current_date = word_slip.from_date
        while current_date <= word_slip.to_date:
            check_in = self._float_time_to_local_datetime(current_date, word_slip.time_to)
            check_out = self._float_time_to_local_datetime(current_date, word_slip.time_from)
            if check_in and check_out and check_out <= check_in:
                check_out += timedelta(days=1)
            pairs.append((self._to_utc_datetime(check_in), self._to_utc_datetime(check_out)))
            current_date += timedelta(days=1)
        return pairs

    def _get_time_word_slips_in_window(self, employee, window_start_utc, window_end_utc):
        if not employee or not window_start_utc or not window_end_utc:
            return self.env['word.slip']

        window_start_local = self._to_local_datetime(window_start_utc)
        window_end_local = self._to_local_datetime(window_end_utc)
        word_slips = self.env['word.slip'].sudo().search([
            ('from_date', '<=', window_end_local.date()),
            ('to_date', '>=', window_start_local.date() - timedelta(days=1)),
            ('type.date_and_time', '=', 'time'),
            ('word_slip.status', '=', 'done'),
        ])
        word_slips = word_slips.filtered(
            lambda x: (x.word_slip.employee_id and x.word_slip.employee_id.id == employee.id) or (
                    x.word_slip.employee_ids and employee.id in x.word_slip.employee_ids.ids))
        return word_slips.filtered(
            lambda line: any(
                window_start_utc <= point <= window_end_utc
                for pair in self._get_time_word_slip_pairs_utc(line)
                for point in pair
                if point
            )
        )

    # Lấy thông tin check-in và check-out của nhân viên
    @api.depends('employee_id', 'time_check_in', 'time_check_out', 'check_no_in', 'check_no_out')
    def _get_check_in_out(self):
        for r in self:
            r.check_in, r.check_out = None, None
            if not r.time_check_in or not r.time_check_out or not r.employee_id:
                continue

            windows = self._get_attendance_priority_windows_utc(r)
            search_start = min(
                window[0]
                for window in windows.values()
                if window and window[0]
            ) if windows else r.time_check_in
            search_end = max(
                window[1]
                for window in windows.values()
                if window and window[1]
            ) if windows else r.time_check_out

            attendance_times = self.env['master.data.attendance'].sudo().search_read(
                [('attendance_time', '>=', search_start),
                 ('attendance_time', '<=', search_end),
                 ('employee_id', '=', r.employee_id.id)],
                ['attendance_time'],
                order='attendance_time ASC'
            )
            attendance_values = [a['attendance_time'] for a in attendance_times if a['attendance_time']]
            preferred_ci = self._filter_attendance_values_in_window(
                attendance_values, windows.get('check_in_preferred', (None, None))
            )
            fallback_ci = self._filter_attendance_values_in_window(
                attendance_values, windows.get('check_in_fallback', (None, None))
            )
            preferred_co = self._filter_attendance_values_in_window(
                attendance_values, windows.get('check_out_preferred', (None, None))
            )
            fallback_co = self._filter_attendance_values_in_window(
                attendance_values, windows.get('check_out_fallback', (None, None))
            )

            check_in = preferred_ci[0] if preferred_ci else (fallback_ci[0] if fallback_ci else None)
            check_out = preferred_co[-1] if preferred_co else (fallback_co[-1] if fallback_co else None)

            in_outs = self._get_time_word_slips_in_window(r.employee_id, r.time_check_in, r.time_check_out)
            for in_out in in_outs:
                for ci, co in self._get_time_word_slip_pairs_utc(in_out):
                    if (ci and r.time_check_in <= ci <= r.time_check_out and r.check_no_in and ci <= r.check_no_in
                            and (not check_in or check_in > ci)):
                        check_in = ci

                    if (co and r.time_check_in <= co <= r.time_check_out and r.check_no_out and co > r.check_no_out
                            and (not check_out or check_out < co)):
                        check_out = co

            r.check_in = check_in
            r.check_out = check_out

    # Lấy thông tin xem nhân viên có check-in hay check-out hay không
    @api.depends('shift', 'check_out', 'check_in')
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

    # Lấy thông tin số phút nhân viên đi muộn hoặc về sớm
    @api.depends('check_out', 'check_in', 'employee_id')
    def _get_minute_late_early(self):
        for r in self:
            r.minutes_late, r.minutes_early = 0, 0
            if not r.shift or not r.shift.start or not r.shift.end_shift:
                continue

            shift_start_time, shift_end_time = self._get_shift_interval_local(r)
            if not shift_start_time or not shift_end_time:
                continue

            if r.check_in:
                check_in_time = self._to_local_datetime(r.check_in)
                if check_in_time > shift_start_time:
                    r.minutes_late = int((check_in_time - shift_start_time).total_seconds() / 60)

            if r.check_out:
                check_out_time = self._to_local_datetime(r.check_out)
                if check_out_time < shift_end_time:
                    r.minutes_early = int((shift_end_time - check_out_time).total_seconds() / 60)

            if r.leave > 0 or r.compensatory > 0 or r.vacation > 0:
                r.minutes_early = 0
                r.minutes_late = 0

            weekday = r.date.weekday()
            week_number = r.date.isocalendar()[1]

            if (r.shift.shift_ot) or (
                    r.shift.is_office_hour and (weekday == 6 or (weekday == 5 and week_number % 2 == 1))):
                r.minutes_early = 0
                r.minutes_late = 0

    # Lấy thông tin ngày công của nhân viên
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
    @api.depends('date', 'check_in', 'check_out', 'minutes_late', 'minutes_early')
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

    def send_fcm_notification(self, title, content, token, user_id, type, employee_id, application_id,
                              screen="/notification", badge=1):
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
        self.queue_job_miss_work()

    def queue_job_miss_work(self):
        today = date.today()
        today_str = today.strftime("%d/%m/%y")

        list_record = self.sudo().search([('date', '=', today)])

        list_record = list_record.filtered(lambda x: bool(x.note) and x.note in ('no_in', 'no_out', 'no_shift'))
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
        list_recs = self.search(domain)
        if list_recs:
            for recs in list_recs:
            # ghi lại để force recompute store fields
                recs.sudo().write({'date': recs.date})  # ghi lại trường date để kích hoạt recompute store
                # hoặc gọi recompute cụ thể
                recs._get_shift_employee()
                recs._get_time_off()
                recs._get_time_in_out()
                recs._check_no_in_out()
                recs._get_check_in_out()
                recs.get_hours_reinforcement()
                recs._get_minute_late_early()
                recs._get_work_day()
                recs.get_department()

        overtime_domain = []
        if date_from:
            overtime_domain.append(('date', '>=', fields.Date.to_date(date_from) - timedelta(days=1)))
        if date_to:
            overtime_domain.append(('date', '<=', fields.Date.to_date(date_to) + timedelta(days=1)))
        if overtime_domain:
            overtime_records = self.env['overtime.rel'].sudo().search(overtime_domain).mapped('overtime_id')
            overtime_records = overtime_records.filtered(
                lambda overtime: (overtime.employee_id and overtime.employee_id.id == emp_id) or
                                 (overtime.employee_ids and emp_id in overtime.employee_ids.ids)
            )
            for overtime in overtime_records:
                overtime._sync_actual_compensatory_for_record(overtime)
        return True

    def recompute_for_overtime(self, employee_ids, date_from=None, date_to=None):
        query = """
            SELECT id
            FROM employee_attendance_v2
            WHERE employee_id = ANY(%s)
              AND date >= %s
              AND date <= %s
        """

        self.env.cr.execute(query, (
            employee_ids,
            date_from,
            date_to
        ))

        ids = [r[0] for r in self.env.cr.fetchall()]
        recs = self.env['employee.attendance.v2'].browse(ids)
        if recs:
            recs.sudo()._get_time_in_out()

    def action_export_excel(self, ids):

        records = self.browse(ids)

        if not records:
            return

        first_date = records[0].date
        month = first_date.month
        year = first_date.year

        days_in_month = calendar.monthrange(year, month)[1]

        employees = {}

        for rec in records:

            emp_id = rec.employee_id.id

            if emp_id not in employees:
                employees[emp_id] = {
                    "employee": rec.employee_id,
                    "days": {}
                }

            day = rec.date.day
            employees[emp_id]["days"][day] = rec

        syntic_records = self.env['synthetic.work'].search([
            ('month', '=', month),
            ('year', '=', year)
        ])

        syntic_map = {}

        for s in syntic_records:
            syntic_map[s.employee_id.id] = s

        output = io.BytesIO()

        workbook = xlsxwriter.Workbook(output)
        sheet = workbook.add_worksheet("Cham cong")

        # ================= FORMAT =================

        title_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "font_size": 16
        })

        header_format = workbook.add_format({
            "bold": True,
            "align": "center",
            "valign": "vcenter",
            "border": 1,
            "bg_color": "#4F81BD",  # xanh dương
            "font_color": "white"
        })

        cell_format = workbook.add_format({
            "align": "center",
            "border": 1
        })

        # ================= SET WIDTH =================

        sheet.set_column(0, 0, 6)
        sheet.set_column(1, 1, 15)
        sheet.set_column(2, 2, 30)  # cột tên rộng hơn

        # ================= TITLE =================

        total_columns = 3 + days_in_month + 20

        title = f"BẢNG CHẤM CÔNG THÁNG {month} NĂM {year}".upper()

        sheet.merge_range(0, 0, 3, total_columns, title, title_format)

        # ================= HEADER =================

        header_row1 = 4
        header_row2 = 5

        sheet.write(header_row1, 0, "STT", header_format)
        sheet.write(header_row1, 1, "Mã NV", header_format)
        sheet.write(header_row1, 2, "Họ tên", header_format)

        sheet.write(header_row2, 0, "", header_format)
        sheet.write(header_row2, 1, "", header_format)
        sheet.write(header_row2, 2, "", header_format)

        col = 3

        for d in range(1, days_in_month + 1):
            date_obj = date(year, month, d)
            weekday_map = {
                0: "T2",
                1: "T3",
                2: "T4",
                3: "T5",
                4: "T6",
                5: "T7",
                6: "CN",
            }

            thu = weekday_map[date_obj.weekday()]

            sheet.write(header_row1, col, thu, header_format)
            sheet.write(header_row2, col, d, header_format)

            col += 1

        summary_columns = [
            "Công thử việc",
            "Công luân chuyển",
            "Tổng công",
            "NB",
            "NP",
            "Lễ",
            "Nghỉ TNLĐ",
            "Nghỉ CĐ Cty",
            "Ô Đ TS",
            "Không Lương",
            "Nghỉ không phép",
            "TC thường (x1.5)",
            "TC CN (x2)",
            "TC Lễ (x3)",
            "Total Nhóm tại nhà",
            "Ngừng việc",
            "Cách ly",
            "Online",
            "Ở nhà",
            "Ký nhận"
        ]

        summary_start_col = col

        for name in summary_columns:
            sheet.write(header_row1, col, name, header_format)
            sheet.write(header_row2, col, "", header_format)

            col += 1

        # ================= DATA =================

        row = 6
        stt = 1

        for emp_id, data in employees.items():

            emp = data["employee"]
            days = data["days"]

            syntic = syntic_map.get(emp_id)

            sheet.write(row, 0, stt, cell_format)
            sheet.write(row, 1, emp.employee_code or "", cell_format)
            sheet.write(row, 2, emp.name or "", cell_format)

            sheet.write(row + 1, 0, "", cell_format)
            sheet.write(row + 1, 1, "", cell_format)
            sheet.write(row + 1, 2, "", cell_format)

            col = 3

            for d in range(1, days_in_month + 1):

                rec = days.get(d)

                if rec:

                    if rec.compensatory >= 1:
                        work_day = "1B"

                    elif rec.compensatory == 0.5:
                        work_day = "B/2"

                    elif rec.leave >= 1:
                        work_day = "1P"

                    elif rec.leave == 0.5:
                        work_day = "P/2"

                    elif rec.shift and rec.shift.key:
                        work_day = rec.shift.key

                    else:
                        work_day = rec.work_day

                    sheet.write(row, col, work_day, cell_format)

                    overtime = rec.over_time or ""
                    sheet.write(row + 1, col, overtime, cell_format)

                else:

                    sheet.write(row, col, "", cell_format)
                    sheet.write(row + 1, col, "", cell_format)

                col += 1

            col = summary_start_col
            for i in range(len(summary_columns)):
                sheet.write(row, col + i, "", cell_format)
                sheet.write(row + 1, col + i, "", cell_format)
            if syntic:
                sheet.write(row, col + 0, syntic.probationary_period or 0, cell_format)
                sheet.write(row, col + 1, 0, cell_format)
                sheet.write(row, col + 2, syntic.total_work or 0, cell_format)

                sheet.write(row, col + 3, syntic.compensatory_leave or 0, cell_format)
                sheet.write(row, col + 4, syntic.on_leave or 0, cell_format)
                sheet.write(row, col + 5, syntic.public_leave or 0, cell_format)

                sheet.write(row, col + 9, syntic.unpaid_leave or 0, cell_format)
                sheet.write(row, col + 10, syntic.unpaid_leave or 0, cell_format)

                sheet.write(row + 1, col + 11, syntic.hours_reinforcement or 0, cell_format)
                sheet.write(row + 1, col + 12, syntic.ot_one_hundred_fifty or 0, cell_format)
                sheet.write(row + 1, col + 13, syntic.ot_three_hundred or 0, cell_format)

            row += 2
            stt += 1

        workbook.close()

        output.seek(0)

        file_data = base64.b64encode(output.read())

        attachment = self.env["ir.attachment"].create({
            "name": f"Cham_cong_{month}_{year}.xlsx",
            "type": "binary",
            "datas": file_data,
            "res_model": self._name,
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    # def action_export_excel(self, ids):
    #
    #     if not ids:
    #         return
    #
    #     records = self.browse(ids)
    #
    #     first_date = records[0].date
    #     month = first_date.month
    #     year = first_date.year
    #
    #     days_in_month = calendar.monthrange(year, month)[1]
    #
    #     employees = self._get_employee_days(ids)
    #     syntic_map = self._get_synthetic_data(month, year, employees.keys())
    #
    #     file_data = self._generate_excel(
    #         employees,
    #         syntic_map,
    #         month,
    #         year,
    #         days_in_month
    #     )
    #
    #     attachment = self.env["ir.attachment"].create({
    #         "name": f"Cham_cong_{month}_{year}.xlsx",
    #         "type": "binary",
    #         "datas": file_data,
    #         "res_model": self._name,
    #     })
    #
    #     return {
    #         "type": "ir.actions.act_url",
    #         "url": f"/web/content/{attachment.id}?download=true",
    #         "target": "self",
    #     }
    #
    # def _get_employee_days(self, ids):
    #
    #     query = """
    #         SELECT
    #             id,
    #             employee_id,
    #             date,
    #             compensatory,
    #             leave,
    #             work_day,
    #             over_time,
    #             shift
    #         FROM employee_attendance_v2
    #         WHERE id IN %s
    #     """
    #
    #     self.env.cr.execute(query, (tuple(ids),))
    #     rows = self.env.cr.dictfetchall()
    #
    #     employees = {}
    #
    #     for r in rows:
    #
    #         emp_id = r["employee_id"]
    #
    #         if emp_id not in employees:
    #             employees[emp_id] = {
    #                 "employee": self.env["hr.employee"].browse(emp_id),
    #                 "days": {}
    #             }
    #
    #         day = r["date"].day
    #         employees[emp_id]["days"][day] = r
    #
    #     return employees
    #
    # def _get_synthetic_data(self, month, year, employee_ids):
    #
    #     query = """
    #         SELECT *
    #         FROM synthetic_work
    #         WHERE month = %s
    #         AND year = %s
    #         AND employee_id IN %s
    #     """
    #
    #     self.env.cr.execute(query, (month, year, tuple(employee_ids)))
    #     rows = self.env.cr.dictfetchall()
    #
    #     result = {}
    #
    #     for r in rows:
    #         result[r["employee_id"]] = r
    #
    #     return result
    #
    # def _generate_excel(self, employees, syntic_map, month, year, days_in_month):
    #
    #     output = io.BytesIO()
    #
    #     workbook = xlsxwriter.Workbook(
    #         output,
    #         {"constant_memory": True}
    #     )
    #
    #     sheet = workbook.add_worksheet("Cham cong")
    #
    #     title_format = workbook.add_format({
    #         "bold": True,
    #         "align": "center",
    #         "font_size": 16
    #     })
    #
    #     header_format = workbook.add_format({
    #         "bold": True,
    #         "align": "center",
    #         "border": 1,
    #         "bg_color": "#4F81BD",
    #         "font_color": "white"
    #     })
    #
    #     cell_format = workbook.add_format({
    #         "align": "center",
    #         "border": 1
    #     })
    #
    #     sheet.set_column(0, 0, 6)
    #     sheet.set_column(1, 1, 15)
    #     sheet.set_column(2, 2, 30)
    #     sheet.set_column(3, 3 + days_in_month, 5)
    #
    #     total_columns = 3 + days_in_month + 20
    #
    #     title = f"BẢNG CHẤM CÔNG THÁNG {month} NĂM {year}".upper()
    #
    #     sheet.merge_range(0, 0, 3, total_columns, title, title_format)
    #
    #     header_row1 = 4
    #     header_row2 = 5
    #
    #     sheet.write_row(header_row1, 0, ["STT", "Mã NV", "Họ tên"], header_format)
    #     sheet.write_row(header_row2, 0, ["", "", ""], header_format)
    #
    #     col = 3
    #
    #     for d in range(1, days_in_month + 1):
    #         date_obj = datetime.date(year, month, d)
    #         thu = date_obj.strftime("%a")
    #
    #         sheet.write(header_row1, col, thu, header_format)
    #         sheet.write(header_row2, col, d, header_format)
    #
    #         col += 1
    #
    #     summary_start_col = col
    #
    #     row = 6
    #     stt = 1
    #
    #     for emp_id, data in employees.items():
    #
    #         emp = data["employee"]
    #         days = data["days"]
    #         syntic = syntic_map.get(emp_id)
    #
    #         sheet.write_row(row, 0, [stt, emp.employee_code or "", emp.name], cell_format)
    #         sheet.write_row(row + 1, 0, ["", "", ""], cell_format)
    #
    #         day_row = []
    #         ot_row = []
    #
    #         for d in range(1, days_in_month + 1):
    #
    #             rec = days.get(d)
    #
    #             if rec:
    #
    #                 if rec["compensatory"] >= 1:
    #                     work_day = "1B"
    #
    #                 elif rec["compensatory"] == 0.5:
    #                     work_day = "B/2"
    #
    #                 elif rec["leave"] >= 1:
    #                     work_day = "1P"
    #
    #                 elif rec["leave"] == 0.5:
    #                     work_day = "P/2"
    #
    #                 else:
    #                     work_day = rec["work_day"]
    #
    #                 day_row.append(work_day)
    #                 ot_row.append(rec["over_time"] or "")
    #
    #             else:
    #                 day_row.append("")
    #                 ot_row.append("")
    #
    #         sheet.write_row(row, 3, day_row, cell_format)
    #         sheet.write_row(row + 1, 3, ot_row, cell_format)
    #
    #         if syntic:
    #
    #             summary = [
    #                 syntic["probationary_period"],
    #                 0,
    #                 syntic["total_work"],
    #                 syntic["compensatory_leave"],
    #                 syntic["on_leave"],
    #                 syntic["public_leave"],
    #                 0,
    #                 0,
    #                 0,
    #                 syntic["unpaid_leave"],
    #                 syntic["unpaid_leave"],
    #                 "",
    #                 "",
    #                 "",
    #                 0, 0, 0, 0, 0, ""
    #             ]
    #
    #         else:
    #
    #             summary = [""] * 20
    #
    #         sheet.write_row(row, summary_start_col, summary, cell_format)
    #
    #         row += 2
    #         stt += 1
    #
    #     workbook.close()
    #
    #     output.seek(0)
    #
    #     return base64.b64encode(output.read())
