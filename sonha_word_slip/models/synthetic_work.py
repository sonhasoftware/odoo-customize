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

    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    month = fields.Integer("Tháng", compute="get_this_month")
    year = fields.Integer("Năm", compute="get_this_month")

    key = fields.Boolean("Khóa công", default=False)

    @api.depends('employee_id', 'month')
    def get_date_work(self):
        for r in self:
            if r.employee_id and r.start_date and r.end_date:
                # Sử dụng read_group để tính toán tổng số dữ liệu trực tiếp
                grouped_data = self.env['employee.attendance'].sudo().read_group(
                    domain=[
                        ('employee_id', '=', r.employee_id.id),
                        ('date', '>=', r.start_date),
                        ('date', '<=', r.end_date)
                    ],
                    fields=['work_day:sum', 'leave:sum', 'compensatory:sum',
                            'over_time:sum', 'minutes_late:sum',
                            'minutes_early:sum', 'public_leave:sum'],
                    groupby=[]
                )
                if grouped_data:
                    data = grouped_data[0]
                    r.date_work = data.get('work_day', 0)
                    r.on_leave = data.get('leave', 0)
                    r.compensatory_leave = data.get('compensatory', 0)
                    r.hours_reinforcement = data.get('over_time', 0)
                    r.number_minutes_late = data.get('minutes_late', 0)
                    r.number_minutes_early = data.get('minutes_early', 0)
                    r.public_leave = data.get('public_leave', 0)
                else:
                    # Gán mặc định khi không có dữ liệu
                    r.date_work = 0
                    r.on_leave = 0
                    r.compensatory_leave = 0
                    r.hours_reinforcement = 0
                    r.number_minutes_late = 0
                    r.number_minutes_early = 0
                    r.public_leave = 0
            else:
                # Gán mặc định khi thiếu thông tin cần thiết
                r.date_work = 0
                r.on_leave = 0
                r.compensatory_leave = 0
                r.hours_reinforcement = 0
                r.number_minutes_late = 0
                r.number_minutes_early = 0
                r.public_leave = 0

    @api.depends('on_leave', 'compensatory_leave', 'public_leave')
    def get_leave(self):
        for r in self:
            r.paid_leave = r.on_leave + r.compensatory_leave + r.public_leave

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

