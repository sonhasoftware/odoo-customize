from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta


class EmployeeAttendance(models.Model):
    _name = 'employee.attendance'
    _description = 'Employee Attendance'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, store=True)
    date = fields.Date(string='Attendance Date', required=True, store=True)
    check_in = fields.Datetime(string='Check In', compute="_get_check_in_out")
    check_out = fields.Datetime(string='Check Out', compute="_get_check_in_out")
    duration = fields.Float("Giờ công", compute="_get_duration")
    shift = fields.Many2one('config.shift', compute="_get_shift_employee")
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

    def update_attendance_data(self):
        employees = self.env['hr.employee'].search([])
        current_date = datetime.now()
        start_date = current_date.replace(day=1) + timedelta(hours=7)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

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

    @api.depends('date', 'employee_id', 'employee_id.shift')
    def _get_shift_employee(self):
        for r in self:
            shift = self.env['register.shift.rel'].sudo().search([('register_shift.employee_id', '=', r.employee_id.id),
                                                                  ('date', '=', r.date)])
            if shift:
                r.shift = shift.shift.id
            elif r.employee_id.shift:
                r.shift = r.employee_id.shift.id
            else:
                r.shift = None

    @api.depends('shift')
    def _get_time_in_out(self):
        for r in self:
            if r.shift:
                time_ci = r.shift.start.time()
                time_co = r.shift.end_shift .time()
                date = r.date
                check_time_ci = datetime.combine(date, time_ci)
                check_time_co = datetime.combine(date, time_co)
                if not r.shift.night:
                    r.time_check_in = check_time_ci - timedelta(minutes=r.shift.earliest_out)
                    r.time_check_out = check_time_co + timedelta(minutes=r.shift.latest_out)
                if r.shift.night:
                    r.time_check_in = check_time_ci - timedelta(minutes=r.shift.earliest_out)
                    check_out = check_time_co + timedelta(minutes=r.shift.latest_out)
                    if (r.time_check_in + timedelta(hours=7)).date() == (check_out + timedelta(hours=7)).date():
                        r.time_check_out = check_out + timedelta(days=1)
                    else:
                        r.time_check_out = check_out
            else:
                r.time_check_in = None
                r.time_check_out = None

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

    def _get_attendance(self):
        for r in self:
            if (not r.check_in and not r.check_out) or (r.check_in and r.check_out):
                r.note = None
            elif not r.check_in:
                r.note = 'no_in'
            elif not r.check_out:
                r.note = 'no_out'

    def _get_minute_late_early(self):
        for r in self:
            if r.shift:
                if r.check_in and (r.check_in + timedelta(hours=7)).time() > (r.shift.start + timedelta(hours=7)).time():
                    check_in_time = datetime.combine(r.check_in.date(), r.check_in.time())
                    shift_start_time = datetime.combine(r.check_in.date(), r.shift.start.time())

                    minute_late = (check_in_time + timedelta(hours=7)) - (shift_start_time + timedelta(hours=7))
                    r.minutes_late = minute_late.total_seconds() / 60
                else:
                    r.minutes_late = 0
                if r.check_out and (r.check_out + timedelta(hours=7)).time() < (r.shift.end_shift + timedelta(hours=7)).time():
                    check_out_time = datetime.combine(r.check_out.date(), r.check_out.time())
                    shift_end_time = datetime.combine(r.check_out.date(), r.shift.end_shift.time())

                    minute_early = (shift_end_time + timedelta(hours=7)) - (check_out_time + + timedelta(hours=7))
                    r.minutes_early = minute_early.total_seconds() / 60
                else:
                    r.minutes_early = 0
            else:
                r.minutes_late = 0
                r.minutes_early = 0

    def _get_work_day(self):
        for r in self:
            work_leave = self.env['word.slip'].sudo().search([
                ('employee_id', '=', r.employee_id.id),
                ('from_date', '<=', r.date),
                ('to_date', '>=', r.date),
                ('level', '=', 'full_day')
            ])
            work_leave = work_leave.filtered(lambda x: x.type.paid == True)
            public_holiday = self.env['resource.calendar.leaves'].sudo().search([])
            public_holiday = public_holiday.filtered(lambda x: x.date_from.date() <= r.date <= x.date_to.date())
            if public_holiday:
                r.work_day = 1
            elif work_leave:
                r.work_day = 1
            elif r.check_in or r.check_out:
                r.work_day = 1
            else:
                r.work_day = 0
