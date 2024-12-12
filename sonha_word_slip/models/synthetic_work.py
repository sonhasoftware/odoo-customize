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
        list_record = self.env['synthetic.work'].sudo().search(['|',
                                                                ('month', '=', current_date.month),
                                                                ('month', '=', current_date.month - 1)])

        if not list_record:
            return

        # Lấy tất cả các employee_id và khoảng thời gian
        employee_ids = list_record.mapped('employee_id.id')
        start_dates = {record.employee_id.id: record.start_date for record in list_record}
        end_dates = {record.employee_id.id: record.end_date for record in list_record}

        # Truy vấn dữ liệu tổng hợp với SQL
        query = """
            SELECT
                employee_id,
                SUM(work_day) AS total_work_day,
                SUM(leave) AS total_leave,
                SUM(compensatory) AS total_compensatory,
                SUM(over_time) AS total_over_time,
                SUM(minutes_late) AS total_minutes_late,
                SUM(minutes_early) AS total_minutes_early,
                SUM(public_leave) AS total_public_leave
            FROM employee_attendance
            WHERE employee_id IN %s AND date >= %s AND date <= %s
            GROUP BY employee_id
        """
        params = (tuple(employee_ids), min(start_dates.values()), max(end_dates.values()))
        self.env.cr.execute(query, params)
        results = self.env.cr.fetchall()

        # Tạo dictionary để tra cứu nhanh
        aggregated_data = {res[0]: res[1:] for res in results}

        # Gán giá trị lại cho các bản ghi synthetic.work
        for record in list_record:
            data = aggregated_data.get(record.employee_id.id, [0] * 7)
            record.date_work = data[0]
            record.on_leave = data[1]
            record.compensatory_leave = data[2]
            record.hours_reinforcement = data[3]
            record.number_minutes_late = data[4]
            record.number_minutes_early = data[5]
            record.public_leave = data[6]

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

