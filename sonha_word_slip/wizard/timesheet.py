from odoo import models, fields
import datetime


class Timesheet(models.TransientModel):
    _name = 'timesheet'

    department = fields.Many2one('hr.department', string="Phòng ban")
    company = fields.Many2one('res.company', string="Công ty")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    def action_confirm(self):
        if self.department:
            list_emp = self.env['hr.employee'].sudo().search([('department_id', '=', self.department.id)])
        if self.company:
            list_emp = self.env['hr.employee'].sudo().search([('company_id', '=', self.company.id)])
        for emp in list_emp:
            date_work, number_minutes_late, number_minutes_early = self.working_day(emp, self.start_date, self.end_date)
            public_holiday, on_leave = self.get_holiday(emp, self.start_date, self.end_date)
            vals = {
                'employee_id': emp.id,
                'department_id': emp.department_id.id,

                'date_work': date_work,
                'apprenticeship': 0,
                'probationary_period': 0,
                'ot_one_hundred': 0,
                'ot_one_hundred_fifty': 0,
                'ot_three_hundred': 0,
                'paid_leave': 0,
                'number_minutes_late': number_minutes_late,
                'number_minutes_early': number_minutes_early,

                'on_leave': on_leave,
                'compensatory_leave': 0,
                'filial_leave': 0,
                'grandparents_leave': 0,
                'vacation': 0,
                'public_leave': public_holiday,

                'start_date': str(self.start_date),
                'end_date': str(self.end_date),

            }
            check_emp = self.env['synthetic.work'].sudo().search([('employee_id', '=', emp.id),
                                                                  ('start_date', '=', self.start_date),
                                                                  ('end_date', '=', self.end_date)])
            if not check_emp:
                self.env['synthetic.work'].sudo().create(vals)
            else:
                check_emp.sudo().write(vals)

    def working_day(self, emp, start, end):
        date_work = 0
        number_minutes_late = 0
        number_minutes_early = 0
        data_work = self.env['employee.attendance'].sudo().search([('employee_id', '=', emp.id),
                                                                   ('date', '>=', start),
                                                                   ('date', '<=', end)])
        if data_work:
            date_work = sum(data_work.mapped('work_day'))
            number_minutes_late = sum(data_work.mapped('minutes_late'))
            number_minutes_early = sum(data_work.mapped('minutes_early'))
        return date_work, number_minutes_late, number_minutes_early

    def get_holiday(self, emp, start, end):
        public_holiday = 0
        on_leave = 0
        public_leave = self.env['resource.calendar.leaves'].sudo().search([])
        leave = self.env['word.slip'].sudo().search([('employee_id', '=', emp.id),
                                                     ('from_date', '<=', end),
                                                     ('to_date', '>=', start)])
        if public_leave:
            public_leave = public_leave.filtered(lambda x: x.date_from.date() <= end and x.date_to.date() >= start)
            public_holiday = len(public_leave)
        if leave:
            on_leave = sum(leave.mapped('duration'))
        return public_holiday, on_leave




