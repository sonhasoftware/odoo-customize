from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from datetime import datetime, time, timedelta


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
    public_leave = fields.Float("Nghỉ lễ", cumpute="get_date_work")

    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    month = fields.Integer("Tháng", compute="get_this_month")
    year = fields.Integer("Năm", compute="get_this_month")

    key = fields.Boolean("Khóa công", default=False)

    # @api.depends('employee_id', 'month')
    # def get_date_work(self):
    #     for r in self:
    #         work = self.env['employee.attendance'].sudo().search([('employee_id', '=', r.employee_id.id),
    #                                                               ('month', '=', r.month),
    #                                                               ('year', '=', r.year)])
    #         if work:
    #             r.date_work = sum(work.mapped('work_day'))
    #             r.on_leave = sum(work.mapped('leave'))
    #             r.compensatory_leave = sum(work.mapped('compensatory'))
    #             r.hours_reinforcement = sum(work.mapped('over_time'))
    #             r.number_minutes_late = sum(work.mapped('minutes_late'))
    #             r.number_minutes_early = sum(work.mapped('minutes_early'))
    #             r.public_leave = sum(work.mapped('public_leave'))
    #         else:
    #             r.date_work = 0
    #             r.on_leave = 0
    #             r.compensatory_leave = 0
    #             r.hours_reinforcement = 0
    #             r.number_minutes_late = 0
    #             r.number_minutes_early = 0
    #             r.public_leave = 0
    #
    # def get_leave(self):
    #     for r in self:
    #         r.paid_leave = r.on_leave + r.compensatory_leave + r.public_leave

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

    # def create_synthetic(self):
    #     employees = self.env['hr.employee'].search([('id', '!=', 1)])
    #     current_date = datetime.now()
    #     start_date = current_date.replace(day=1) + timedelta(hours=7)
    #     end_date = (start_date + relativedelta(months=1)) - timedelta(days=1)
    #     for employee in employees:
    #         synthetic = self.env['synthetic.work'].sudo().search([('month', '=', current_date.month),
    #                                                               ('year', '=', current_date.year),
    #                                                               ('employee_id', '=', employee.id)])
    #         if not synthetic:
    #             self.env['synthetic.work'].create({
    #                 'employee_id': employee.id,
    #                 'department_id': employee.department_id.id,
    #                 'start_date': str(start_date),
    #                 'end_date': str(end_date),
    #             })

