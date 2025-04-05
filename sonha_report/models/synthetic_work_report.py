from odoo import api, fields, models

class SyntheticWorkReport(models.Model):
    _name = 'synthetic.work.report'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên")
    employee_code = fields.Char("Mã nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")

    date_work = fields.Float("Ngày làm việc")
    apprenticeship = fields.Float("Công học việc")
    probationary_period = fields.Float("Công thử việc")
    ot_one_hundred = fields.Float("Giờ làm thêm hưởng 100%")
    ot_one_hundred_fifty = fields.Float("Giờ làm thêm hưởng 150%")
    ot_three_hundred = fields.Float("Giờ làm thêm hưởng 300%")
    paid_leave = fields.Float("Ngày nghỉ hưởng 100% lương")
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
    total_work = fields.Float("Tổng công")
    month = fields.Integer("Tháng")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
    hours_reinforcement = fields.Float("Giờ tăng cường")
