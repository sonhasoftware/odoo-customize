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
                    total_leave_balance_left = self.caculate_total_leave_balance_left(emp)
                    personal_records = list_records.filtered(lambda x: x.employee_id.id == emp.id)
                    if personal_records:
                        for r in personal_records:
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


    def caculate_total_leave_balance_left(self, emp):
        base_timeline = date(2023, 12, 31)
        base_leave_balance = 4
        old_leave_balance = base_leave_balance
        begin_date = self.from_date
        base_year = base_timeline.year
        begin_year = begin_date.year
        caculate_date_1 = date(begin_year, 6, 30)
        caculate_date_2 = (begin_date + relativedelta(years=-1)).replace(month=12, day=31)
        if begin_date >= base_timeline:
            while base_year < begin_year - 1:
                caculate_time_1 = (base_timeline + relativedelta(years=1)).replace(month=6, day=30)
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>=', base_timeline),
                                                                            ('date', '<=', caculate_time_1),
                                                                            ('employee_id', '=', emp.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                new_leave_balance = old_leave_balance + 6 - total_used_leave
                if new_leave_balance >= 6:
                    new_leave_balance = 6
                caculate_time_2 = (base_timeline + relativedelta(years=1)).replace(month=12, day=31)
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>', caculate_time_1),
                                                                            ('date', '<=', caculate_time_2),
                                                                            ('employee_id', '=', emp.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                new_leave_balance = new_leave_balance + 6 - total_used_leave
                old_leave_balance = new_leave_balance
                base_year = base_year + 1
                base_timeline = base_timeline + relativedelta(years=1)
            begin_nonth = begin_date.month
            if begin_nonth <= 6:
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>', caculate_date_2),
                                                                            ('date', '<', begin_date),
                                                                            ('employee_id', '=', emp.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                start_time = begin_date.replace(month=1, day=1)
                start_time = datetime.strptime(start_time.strftime("%Y-%m-%d"), "%Y-%m-%d")
                end_time = datetime.strptime(begin_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                diff = relativedelta(end_time, start_time)
                months_difference = diff.months + 1
                total_leave_left = old_leave_balance + months_difference - total_used_leave
            else:
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>', caculate_date_2),
                                                                            ('date', '<=', caculate_date_1),
                                                                            ('employee_id', '=', emp.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                total_leave_left = old_leave_balance + 6 - total_used_leave
                if total_leave_left >= 6:
                    total_leave_left = 6
                used_leave = self.env['employee.attendance'].sudo().search([('date', '>', caculate_date_1),
                                                                            ('date', '<', begin_date),
                                                                            ('employee_id', '=', emp.id)])
                total_used_leave = sum(used_leave.mapped('leave')) if used_leave else 0
                start_time = begin_date.replace(month=1, day=1)
                start_time = datetime.strptime(caculate_date_1.strftime("%Y-%m-%d"), "%Y-%m-%d")
                end_time = datetime.strptime(begin_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
                diff = relativedelta(end_time, start_time)
                months_difference = diff.months + 1
                total_leave_left = total_leave_left + months_difference - total_used_leave
            return total_leave_left
        else:
            return 0











