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

    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    work_hc = fields.Float("Công hành chính")
    work_sp = fields.Float("Công Sản phẩm")

    overtime_nb = fields.Float("Giờ làm thêm hưởng nghỉ bù")

    month = fields.Integer("Tháng", compute="get_this_month", store=True)
    year = fields.Integer("Năm", compute="get_this_month")

    key = fields.Boolean("Khóa công", default=False)

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
                    COALESCE(SUM(over_time_nb), 0) AS over_time_nb
                FROM employee_attendance_store
                WHERE employee_id = %s
                  AND date >= %s
                  AND date <= %s
            """

            self.env.cr.execute(query, (r.employee_id.id, r.start_date, r.end_date))
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

    @api.depends('on_leave', 'compensatory_leave', 'public_leave', 'maternity_leave', 'wedding_leave')
    def get_leave(self):
        for r in self:
            r.paid_leave = r.on_leave + r.compensatory_leave + r.public_leave + r.filial_leave + r.grandparents_leave + r.maternity_leave + r.wedding_leave

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

