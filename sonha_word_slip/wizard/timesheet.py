from odoo import models, fields
import datetime


class Timesheet(models.TransientModel):
    _name = 'timesheet'

    department = fields.Many2one('hr.department', string="Phòng ban")
    company = fields.Many2one('res.company', string="Công ty")
    month = fields.Selection([('one', 1),
                              ('two', 2),
                              ('three', 3),
                              ('four', 4),
                              ('five', 5),
                              ('six', 6),
                              ('seven', 7),
                              ('eight', 8),
                              ('nigh', 9),
                              ('ten', 10),
                              ('eleven', 11),
                              ('twenty', 12), ], string="Tháng", required=True)
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year, required=True)

    def action_confirm(self):
        if self.month == 'one':
            month = 1
        elif self.month == 'two':
            month = 2
        elif self.month == 'three':
            month = 3
        elif self.month == 'four':
            month = 4
        elif self.month == 'five':
            month = 5
        elif self.month == 'six':
            month = 6
        elif self.month == 'seven':
            month = 7
        elif self.month == 'eight':
            month = 8
        elif self.month == 'nigh':
            month = 9
        elif self.month == 'ten':
            month = 10
        elif self.month == 'eleven':
            month = 11
        elif self.month == 'twenty':
            month = 12
        if self.department:
            list_emp = self.env['hr.employee'].sudo().search([('department_id', '=', self.department.id)])
        if self.company:
            list_emp = self.env['hr.employee'].sudo().search([('company_id', '=', self.company.id)])
        for emp in list_emp:
            lock_key = self.env['synthetic.work'].sudo().search([('employee_id', '=', emp.id),
                                                                 ('month', '=', month),
                                                                 ('year', '=', self.year)])
            lock_key.key = True

    # def working_day(self, emp, start, end):
    #     date_work = 0
    #     number_minutes_late = 0
    #     number_minutes_early = 0
    #     data_work = self.env['employee.attendance'].sudo().search([('employee_id', '=', emp.id),
    #                                                                ('date', '>=', start),
    #                                                                ('date', '<=', end)])
    #     if data_work:
    #         date_work = sum(data_work.mapped('work_day'))
    #         number_minutes_late = sum(data_work.mapped('minutes_late'))
    #         number_minutes_early = sum(data_work.mapped('minutes_early'))
    #     return date_work, number_minutes_late, number_minutes_early
    #
    # def get_holiday(self, emp, start, end):
    #     public_holiday = 0
    #     on_leave = 0
    #     on_compensatory = 0
    #     public_leave = self.env['resource.calendar.leaves'].sudo().search([])
    #     word_sip = self.env['word.slip'].sudo().search([('employee_id', '=', emp.id),
    #                                                     ('from_date', '<=', end),
    #                                                     ('to_date', '>=', start)])
    #     leave = word_sip.filtered(lambda x: x.word_slip.type.name == "Nghỉ phép")
    #     compensatory = word_sip.filtered(lambda x: x.word_slip.type.name == "nghỉ bù")
    #
    #     if public_leave:
    #         public_leave = public_leave.filtered(lambda x: x.date_from.date() <= end and x.date_to.date() >= start)
    #         public_holiday = len(public_leave)
    #     if leave:
    #         on_leave = sum(leave.mapped('duration'))
    #     if compensatory:
    #         on_compensatory = sum(compensatory.mapped('duration'))
    #     return public_holiday, on_leave, on_compensatory
    #
    # def get_hours_reinforcement(self, emp, start, end):
    #     hours_reinforcement = 0
    #     ot = self.env['register.overtime'].sudo().search([('employee_id', '=', emp.id),
    #                                                       ('start_date', '<=', end),
    #                                                       ('end_date', '>=', start)])
    #     if ot:
    #         for r in ot:
    #             if r.start_date == r.end_date:
    #                 total = r.end_time - r.start_time
    #                 hours_reinforcement += total
    #             else:
    #                 start_date = fields.Date.from_string(r.start_date)
    #                 end_date = fields.Date.from_string(r.end_date)
    #                 day_duration = (end_date - start_date).days + 1
    #                 time_duration = r.end_time - r.start_time
    #                 total = time_duration * day_duration
    #                 hours_reinforcement += total
    #     return hours_reinforcement
