from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


class SyntheticWork(models.Model):
    _name = 'synthetic.work'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên")
    employee_code = fields.Char("Mã nhân viên", compute="_get_employee_code")
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)

    workday = fields.Float("Ngày công")
    hours_reinforcement = fields.Float("Giờ tăng cường", compute="get_date_work")
    public_management = fields.Float("Công quản lý")
    ot_management = fields.Float("Giờ làm thêm quản lý")
    service = fields.Float("Công phục vụ")
    ot_service = fields.Float("Giờ làm thêm phục vụ")
    toxic_work = fields.Float("Công độc hại")

    date_work = fields.Float("Ngày làm việc", compute="get_date_work")
    apprenticeship = fields.Float("Công học việc")
    probationary_period = fields.Float("Công thử việc")
    ot_one_hundred = fields.Float("Giờ làm thêm hưởng 100%")
    ot_one_hundred_fifty = fields.Float("Giờ làm thêm hưởng 150%")
    ot_three_hundred = fields.Float("Giờ làm thêm hưởng 300%")
    paid_leave = fields.Float("Ngày nghỉ hưởng 100% lương", compute="get_leave")
    number_minutes_late = fields.Float("Số phút đi muộn", compute="get_date_work")
    number_minutes_early = fields.Float("Số phút về sớm", compute="get_date_work")

    shift_two_crew_three = fields.Float("Số lần làm ca 2 kíp 3")
    shift_three_crew_four = fields.Float("Số lần làm ca 3 kíp 4")
    on_leave = fields.Float("Nghỉ phép", compute="get_date_work")
    compensatory_leave = fields.Float("Nghỉ bù", compute="get_date_work")
    filial_leave = fields.Float("Nghỉ bố mẹ mất")
    grandparents_leave = fields.Float("Nghỉ ông bà mất")
    vacation = fields.Float("Nghỉ mát")
    public_leave = fields.Float("Nghỉ lễ", compute="get_date_work")
    total_work = fields.Float("Tổng công", compute="get_total_work")
    maternity_leave = fields.Float("Nghỉ vợ sinh")
    wedding_leave = fields.Float("Nghỉ cưới")
    paid_leave_slip = fields.Float("Đơn nghỉ có hưởng lương", compute="get_total_work")

    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    work_hc = fields.Float("Công hành chính")
    work_sp = fields.Float("Công Sản phẩm")

    overtime_nb = fields.Float("Giờ làm thêm hưởng nghỉ bù")

    month = fields.Integer("Tháng", compute="get_this_month", store=True)
    year = fields.Integer("Năm", compute="get_this_month")

    key = fields.Boolean("Khóa công", default=False)
    total_time_late = fields.Integer("Tổng số lần đi muộn/về sớm quá 30p")
    actual_work = fields.Float("Công thực tế theo ca", readonly=True)
    standard_work = fields.Float("Công chuẩn", compute='get_standard_work')
    forgot_time = fields.Float("Số lần quên CI/CO")
    late_fine = fields.Float("Vi phạm đi muộn (VNĐ)", compute="_get_late_fine", digits=(16, 0))
    early_fine = fields.Float("Vi phạm về sớm (VNĐ)", compute="_get_early_fine", digits=(16, 0))
    forgot_fine = fields.Float("Vi phạm quên CI/CO (VNĐ)", compute="_get_forgot_fine", digits=(16, 0))
    total_fine = fields.Float("Tổng vi phạm (VNĐ)", compute="_get_total_fine", digits=(16, 0))
    work_eat = fields.Integer("Công ăn")

    @api.depends('department_id', 'month', 'year')
    def get_standard_work(self):
        for r in self:
            work = self.env['config.standard.work'].sudo().search([
                ('department_id', '=', r.department_id.id),
                ('month', '=', r.month),
                ('year', '=', r.year)])
            if work:
                if work.work_apply <= 0:
                    r.standard_work = work.work_actual
                else:
                    r.standard_work = work.work_apply
            else:
                r.standard_work = 0

    @api.depends('employee_id', 'month')
    def get_date_work(self):
        for r in self:
            query = """
                SELECT 
                    COALESCE(SUM(work_day), 0) AS date_work,
                    COALESCE(SUM(leave), 0) AS on_leave,
                    COALESCE(SUM(compensatory), 0) AS compensatory_leave,
                    COALESCE(SUM(over_time), 0) AS hours_reinforcement,
                    COALESCE(SUM(minutes_late), 0) AS number_minutes_late,
                    COALESCE(SUM(minutes_early), 0) AS number_minutes_early,
                    COALESCE(SUM(public_leave), 0) AS public_leave,
                    COALESCE(SUM(c2k3), 0) AS shift_two_crew_three,
                    COALESCE(SUM(c3k4), 0) AS shift_three_crew_four,
                    COALESCE(SUM(shift_toxic), 0) AS toxic_work,
                    COALESCE(SUM(work_hc), 0) AS work_hc,
                    COALESCE(SUM(work_sp), 0) AS work_sp,
                    COALESCE(SUM(over_time_nb), 0) AS over_time_nb,
                    COALESCE(SUM(times_late), 0) AS times_late,
                    COALESCE(SUM(actual_work), 0) AS actual_work,
                    COALESCE(SUM(vacation), 0) AS vacation,
                    COALESCE(SUM(forgot_time), 0) AS forgot_time,
                    COALESCE(SUM(work_eat), 0) AS work_eat,
                    COALESCE(SUM(ot_one_hundred), 0) AS ot_one_hundred,
                    COALESCE(SUM(ot_one_hundred_fifty), 0) AS ot_one_hundred_fifty,
                    COALESCE(SUM(ot_two_hundred), 0) AS ot_two_hundred,
                    COALESCE(SUM(ot_two_hundred_fifty), 0) AS ot_two_hundred_fifty,
                    COALESCE(SUM(ot_three_hundred), 0) AS ot_three_hundred,
                    COALESCE(SUM(unpaid_leave), 0) AS unpaid_leave,
                    COALESCE(SUM(paid_leave_slip), 0) AS paid_leave_slip
                FROM employee_attendance_v2
                WHERE employee_id = %s
                  AND date >= %s
                  AND date <= %s
            """

            self.env.cr.execute(query, (r.employee_id.id, r.start_date or None, r.end_date or None))
            result = self.env.cr.dictfetchone()

            # Gán các giá trị từ kết quả truy vấn
            r.date_work = result['date_work']
            r.on_leave = result['on_leave']
            r.compensatory_leave = result['compensatory_leave']
            r.hours_reinforcement = result['hours_reinforcement']
            r.number_minutes_late = result['number_minutes_late']
            r.number_minutes_early = result['number_minutes_early']
            r.public_leave = result['public_leave']
            r.shift_two_crew_three = result['shift_two_crew_three']
            r.shift_three_crew_four = result['shift_three_crew_four']
            r.toxic_work = result['toxic_work']
            r.work_hc = result['work_hc']
            r.work_sp = result['work_sp']
            r.overtime_nb = result['over_time_nb']
            r.total_time_late = result['times_late']
            r.actual_work = result['actual_work']
            r.vacation = result['vacation']
            r.forgot_time = result['forgot_time']
            r.work_eat = result['work_eat']
            r.unpaid_leave = result['unpaid_leave']
            r.paid_leave_slip = result['paid_leave_slip']

    @api.depends('on_leave', 'compensatory_leave', 'public_leave', 'maternity_leave', 'wedding_leave', 'paid_leave_slip')
    def get_leave(self):
        for r in self:
            r.paid_leave = r.on_leave + r.compensatory_leave + r.public_leave + r.filial_leave + r.grandparents_leave + r.maternity_leave + r.wedding_leave + r.vacation + r.paid_leave_slip

    @api.depends('date_work', 'paid_leave')
    def get_total_work(self):
        for r in self:
            r.total_work = r.date_work + r.paid_leave

    @api.depends('start_date')
    def get_this_month(self):
        for r in self:
            if r.start_date:
                r.month = r.start_date.month
                r.year = r.start_date.year
            else:
                r.month = r.month
                r.year = r.year

    @api.depends('employee_id')
    def _get_employee_code(self):
        for r in self:
            if r.employee_id.employee_code:
                r.employee_code = r.employee_id.employee_code
            else:
                r.employee_code = None

    def create_synthetic(self):
        employees = self.env['hr.employee'].search([('id', '!=', 1)])
        current_date = date.today()
        start_date = current_date.replace(day=1)
        end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)

        start_current = start_date - relativedelta(months=1)
        end_current = (start_current + relativedelta(months=1)) - timedelta(days=1)
        for employee in employees:
            synthetic = self.env['synthetic.work'].sudo().search([('start_date', '=', start_date),
                                                                  ('employee_id', '=', employee.id)])
            if not synthetic:
                self.env['synthetic.work'].create({
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id,
                    'start_date': str(start_date),
                    'end_date': str(end_date),
                })

            synthetic_current = self.env['synthetic.work'].sudo().search([('start_date', '=', start_current),
                                                                          ('employee_id', '=', employee.id)])

            if not synthetic_current:
                self.env['synthetic.work'].create({
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id,
                    'start_date': str(start_current),
                    'end_date': str(end_current),
                })

    @api.depends('number_minutes_late')
    def _get_late_fine(self):
        for r in self:
            r.late_fine = r.number_minutes_late * 5000

    @api.depends('number_minutes_early')
    def _get_early_fine(self):
        for r in self:
            r.early_fine = r.number_minutes_early * 5000

    @api.depends('forgot_time')
    def _get_forgot_fine(self):
        for r in self:
            r.forgot_fine = r.forgot_time * 100000

    @api.depends('forgot_fine', 'early_fine', 'late_fine')
    def _get_total_fine(self):
        for r in self:
            r.total_fine = r.forgot_fine + r.early_fine + r.late_fine

