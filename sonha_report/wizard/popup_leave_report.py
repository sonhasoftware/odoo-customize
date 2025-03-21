from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date
from dateutil.relativedelta import relativedelta

class PopupLeaveReport(models.TransientModel):
    _name = 'popup.leave.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")


    def action_confirm(self):
        self.env['leave.report'].search([]).sudo().unlink()
        list_records = self.env['employee.attendance'].sudo().search([('date', '>=', self.from_date),
                                                                      ('date', '<=', self.to_date)])
        if self.company_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
            if self.department_id:
                list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
                if self.employee_id:
                    list_records = list_records.filtered(lambda x: x.employee_id.id == self.employee_id.id)
            list_records = list_records.filtered(lambda x: x.leave != 0)
            if list_records:
                list_emp = list_records.mapped('employee_id')
                for emp in list_emp:
                    personal_records = list_records.filtered(lambda x: x.employee_id.id == emp.id)
                    if personal_records:
                        for r in personal_records:
                            total_leave_balance_left = self.caculate_begin_period(r)
                            vals = {
                                'employee_id': r.employee_id.id,
                                'department_id': r.department_id.id,
                                'begin_period': total_leave_balance_left,
                                'leave': r.leave,
                                'date': r.date,
                            }
                            self.env['leave.report'].sudo().create(vals)
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Báo cáo phép chi tiết',
                    'res_model': 'leave.report',
                    'view_mode': 'tree',
                    'target': 'current',
                }
            else:
                raise ValidationError("Nhân viên không sử dụng phép trong tháng này!")


    def caculate_begin_period(self, record):
        base_timeline = date(2023, 12, 31)
        base_leave_balance = 4
        old_leave_balance = base_leave_balance
        begin_date = record.date
        base_year = base_timeline.year
        begin_year = begin_date.year
        if begin_date >= base_timeline:
            start_date = base_timeline
            if base_timeline.month <= 6:
                total_leave_left = self.caculate_leave_balance_left(start_date, begin_date, old_leave_balance, record)
                return total_leave_left
            else:
                if base_year < begin_year:
                    end_date = start_date.replace(year=base_year, month=12, day=31)
                else:
                    end_date = begin_date
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>=', start_date),
                                                                            ('date', '<=', end_date),
                                                                            ('employee_id', '=', record.employee_id.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                start_time = datetime.strptime(start_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                end_time = datetime.strptime(end_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                diff = relativedelta(end_time, start_time)
                months_difference = diff.months
                total_leave_left = old_leave_balance + months_difference - total_used_leave
                if base_year < begin_year:
                    start_date = end_date + relativedelta(days=1)
                    total_leave_left = total_leave_left + 1
                    total_leave_left = self.caculate_leave_balance_left(start_date, begin_date, total_leave_left, record)
                return total_leave_left
        else:
            return 0



    def caculate_leave_balance_left(self, start_date, begin_date, old_leave_balance, record):
        base_year = start_date.year
        begin_year = begin_date.year
        while base_year <= begin_year:
            if base_year < begin_year:
                caculate_date_1 = start_date.replace(year=base_year, month=7, day=1)
                caculate_time_1 = start_date.replace(year=base_year, month=6, day=30)
            else:
                if begin_date.month <= 6:
                    caculate_date_1 = begin_date
                    caculate_time_1 = begin_date
                else:
                    caculate_date_1 = start_date.replace(year=base_year, month=7, day=1)
                    caculate_time_1 = start_date.replace(year=base_year, month=6, day=30)
            used_leave = self.env['employee.attendance'].sudo().search([('date', '>=', start_date),
                                                                        ('date', '<', caculate_date_1),
                                                                        ('employee_id', '=', record.employee_id.id)])
            total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
            start_time = datetime.strptime(start_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
            end_date = datetime.strptime(caculate_time_1.strftime("%Y-%m-%d"), "%Y-%m-%d")
            diff = relativedelta(end_date, start_time)
            months_difference = diff.months
            total_leave_left = old_leave_balance + months_difference - total_used_leave
            if base_year < begin_year or begin_date.month > 6:
                if total_leave_left >= 6:
                    total_leave_left = 6
                if base_year < begin_year:
                    caculate_date_2 = start_date.replace(year=base_year, month=12, day=31) + relativedelta(days=1)
                else:
                    if begin_date.month > 6:
                        caculate_date_2 = begin_date
                start_date = caculate_date_1
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>=', start_date),
                                                                            ('date', '<', caculate_date_2),
                                                                            ('employee_id', '=', record.employee_id.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                start_time = datetime.strptime(start_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                caculate_time_2 = datetime.strptime(caculate_date_2.strftime("%Y-%m-%d"), "%Y-%m-%d")
                diff = relativedelta(caculate_time_2, start_time)
                months_difference = diff.months + 1
                total_leave_left = total_leave_left + months_difference - total_used_leave
                old_leave_balance = total_leave_left
                start_date = caculate_date_2
            base_year = base_year + 1
        return total_leave_left













