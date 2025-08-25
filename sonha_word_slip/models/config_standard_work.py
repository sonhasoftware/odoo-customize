from odoo import api, fields, models
from datetime import datetime, timedelta
import calendar


class ConfigStandardWork(models.Model):
    _name = 'config.standard.work'

    department_id = fields.Many2one('hr.department', string="Phòng ban", readonly=True)
    company_id = fields.Many2one('res.company', string="Công ty", readonly=True)
    month = fields.Integer("Tháng", readonly=True)
    year = fields.Integer("Năm", readonly=True)
    work_actual = fields.Float("Công chuẩn hệ thống", readonly=True)
    work_apply = fields.Float("Công chuẩn áp dụng")

    def compute_standard_work(self):
        current_year = datetime.now().year
        departments = self.env['hr.department'].search([])

        for month in range(1, 13):
            first_day = datetime(current_year, month, 1)
            last_day = datetime(current_year, month, calendar.monthrange(current_year, month)[1])

            for dep in departments:
                sat_type = dep.company_id.calender_work
                work_actual = 0

                day = first_day
                while day <= last_day:
                    weekday = day.weekday()  # 0..6
                    if weekday == 6:
                        pass
                    elif weekday == 5:
                        if sat_type == "leave":
                            pass
                        else:
                            wim = (day.day - 1) // 7 + 1  # tuần trong tháng
                            if sat_type == "even" and (wim % 2 == 0):
                                work_actual += 1
                            elif sat_type == "odd" and (wim % 2 == 1):
                                work_actual += 1
                    else:
                        work_actual += 1

                    day += timedelta(days=1)

                existing = self.search([
                    ('department_id', '=', dep.id),
                    ('year', '=', current_year),
                    ('month', '=', month)
                ], limit=1)
                vals = {
                    'department_id': dep.id,
                    'company_id': dep.company_id.id if dep.company_id else self.env.company.id,
                    'year': current_year,
                    'month': month,
                    'work_actual': work_actual,
                    'work_apply': 0,
                }
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
