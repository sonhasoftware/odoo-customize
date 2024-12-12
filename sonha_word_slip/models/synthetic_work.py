from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from datetime import datetime, time, timedelta, date


class SyntheticWork(models.Model):
    _name = 'synthetic.work'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên")
    employee_code = fields.Char("Mã nhân viên", compute="_get_employee_code")
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)

    workday = fields.Float("Ngày công")
    hours_reinforcement = fields.Float("Giờ tăng cường")
    public_management = fields.Float("Công quản lý")
    ot_management = fields.Float("Giờ làm thêm quản lý")
    service = fields.Float("Công phục vụ")
    ot_service = fields.Float("Giờ làm thêm phục vụ")
    toxic_work = fields.Float("Công độc hại")

    date_work = fields.Float("Ngày làm việc")
    apprenticeship = fields.Float("Công học việc")
    probationary_period = fields.Float("Công thử việc")
    ot_one_hundred = fields.Float("Giờ làm thêm hưởng 100%")
    ot_one_hundred_fifty = fields.Float("Giờ làm thêm hưởng 150%")
    ot_three_hundred = fields.Float("Giờ làm thêm hưởng 300%")
    paid_leave = fields.Float("Ngày nghỉ hưởng 100% lương", compute="get_leave")
    number_minutes_late = fields.Float("Số phút đi muộn")
    number_minutes_early = fields.Float("Số phút về sớm")

    shift_two_crew_three = fields.Float("Số lần làm ca 2 kíp 3")
    shift_three_crew_four = fields.Float("Số lần làm ca 3 kíp 4")
    on_leave = fields.Float("Nghỉ phép")
    compensatory_leave = fields.Float("Nghỉ bù")
    filial_leave = fields.Float("Nghỉ bố mẹ mất")
    grandparents_leave = fields.Float("Nghỉ ông bà mất")
    vacation = fields.Float("Nghỉ mát")
    public_leave = fields.Float("Nghỉ lễ")

    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    month = fields.Integer("Tháng", compute="get_this_month")
    year = fields.Integer("Năm", compute="get_this_month")

    key = fields.Boolean("Khóa công", default=False)

    def get_date_work(self):
        current_date = date.today()
        # Lấy tất cả các bản ghi cần xử lý
        list_record = self.env['synthetic.work'].sudo().search(['|',
                                                                ('month', '=', current_date.month),
                                                                ('month', '=', current_date.month - 1)])
        if not list_record:
            return

        # Lấy tất cả employee_id và khoảng thời gian cần xử lý
        employee_ids = list_record.mapped('employee_id.id')
        start_end_dates = {(record.employee_id.id, record.start_date, record.end_date): record for record in
                           list_record}

        # Truy vấn toàn bộ dữ liệu attendance liên quan
        attendance_data = self.env['employee.attendance'].sudo().search_read(
            domain=[
                ('employee_id', 'in', employee_ids),
                ('date', '>=', min(list_record.mapped('start_date'))),
                ('date', '<=', max(list_record.mapped('end_date')))
            ],
            fields=['employee_id', 'date', 'work_day', 'leave', 'compensatory', 'over_time',
                    'minutes_late', 'minutes_early', 'public_leave']
        )

        # Xử lý dữ liệu attendance
        grouped_data = {}
        for record in attendance_data:
            key = (record['employee_id'][0], record['date'])
            if key not in grouped_data:
                grouped_data[key] = {
                    'work_day': 0,
                    'leave': 0,
                    'compensatory': 0,
                    'over_time': 0,
                    'minutes_late': 0,
                    'minutes_early': 0,
                    'public_leave': 0
                }
            grouped_data[key]['work_day'] += record['work_day']
            grouped_data[key]['leave'] += record['leave']
            grouped_data[key]['compensatory'] += record['compensatory']
            grouped_data[key]['over_time'] += record['over_time']
            grouped_data[key]['minutes_late'] += record['minutes_late']
            grouped_data[key]['minutes_early'] += record['minutes_early']
            grouped_data[key]['public_leave'] += record['public_leave']

        # Gán giá trị cho từng bản ghi synthetic.work
        for (employee_id, start_date, end_date), synthetic_work in start_end_dates.items():
            relevant_data = [v for (eid, date), v in grouped_data.items() if
                             eid == employee_id and start_date <= date <= end_date]

            synthetic_work.date_work = sum([d['work_day'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.on_leave = sum([d['leave'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.compensatory_leave = sum([d['compensatory'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.hours_reinforcement = sum([d['over_time'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.number_minutes_late = sum([d['minutes_late'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.number_minutes_early = sum(
                [d['minutes_early'] for d in relevant_data]) if relevant_data else 0
            synthetic_work.public_leave = sum([d['public_leave'] for d in relevant_data]) if relevant_data else 0

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

