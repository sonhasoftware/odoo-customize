from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date
from dateutil.relativedelta import relativedelta

class PopupSyntheticLeaveReport(models.TransientModel):
    _name = 'popup.synthetic.leave.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")

    @api.constrains('from_date', 'to_date')
    def validate_from_to_date(self):
        now = datetime.now().date()
        for r in self:
            if r.from_date and r.to_date:
                if r.from_date.month != r.to_date.month or r.from_date.year != r.to_date.year:
                    raise ValidationError("Chỉ được chọn ngày trong cùng 1 tháng!")
                if r.from_date > r.to_date:
                    raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc!")
            if r.from_date and r.from_date > now:
                raise ValidationError("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày hiện tại!")

    def action_confirm(self):
        self.env['synthetic.leave.report'].search([]).sudo().unlink()
        if self.company_id and not self.department_id:
            list_employee = self.env['hr.employee'].sudo().search([('company_id', '=', self.company_id.id)])
        if self.department_id and not self.employee_id:
            list_employee = self.env['hr.employee'].sudo().search([('department_id', '=', self.department_id.id)])
        if self.employee_id:
            list_employee = self.env['hr.employee'].sudo().search([('id', '=', self.employee_id.id)])
        eliminated_employee = []
        from_date = self.from_date.replace(day=1)
        to_date = from_date + relativedelta(months=1, days=-1)
        for emp in list_employee:
            if emp.leave_milestone_date and self.from_date >= emp.leave_milestone_date:
                total_leave_balance_left, total_leave = self.re_calculate_leave_left(emp, self.from_date)
                leave_left = total_leave_balance_left - total_leave
                vals = {
                    'employee_id': emp.id,
                    'department_id': emp.department_id.id,
                    'begin_period': total_leave_balance_left,
                    'leave': total_leave,
                    'from_date': from_date,
                    'to_date': to_date,
                    'total_leave_left': leave_left
                }
                self.env['synthetic.leave.report'].sudo().create(vals)
            else:
                eliminated_employee.append(emp.name)
        if eliminated_employee:
            employee_name = ', '.join(eliminated_employee)
            self.env['bus.bus']._sendone(
                (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
                'simple_notification',
                {
                    'title': "Cảnh báo!",
                    'message': f"Không tìm thấy mốc thời gian phép của nhân viên {employee_name} hoặc mốc thời gian lớn hơn thời gian chọn báo cáo",
                    'sticky': False,
                }
            )
        return {
            'type': 'ir.actions.act_window',
            'name': 'Báo cáo phép tổng hợp',
            'res_model': 'synthetic.leave.report',
            'view_mode': 'tree',
            'target': 'current',
        }

    def calculate_used_leave(self, emp, start_time, end_time):
        records = self.env['employee.attendance'].sudo().search([('employee_id', '=', emp.id),
                                                                 ('date', '>=', start_time),
                                                                 ('date', '<=', end_time)])
        count = sum(records.filtered(lambda x: x.leave != 0).mapped('leave'))
        return count

    def init_leave_left(self, emp, base_time, old_leave_balance):
        month_fields = ['th_1', 'th_2', 'th_3', 'th_4', 'th_5', 'th_6', 'th_7',
                        'th_8', 'th_9', 'th_10', 'th_11', 'th_12']
        leave_used_fields = ['leave_t1', 'leave_t2', 'leave_t3', 'leave_t4', 'leave_t5', 'leave_t6', 'leave_t7',
                             'leave_t8', 'leave_t9', 'leave_t10', 'leave_t11', 'leave_t12']
        leave_record = self.env['leave.left'].sudo().search([('employee_id', '=', emp.id),
                                                             ('year', '=', base_time.year)])
        if not leave_record:
            leave_record = self.env['leave.left'].sudo().create({
                'employee_id': emp.id,
                'year': base_time.year,
                'start_date': str(base_time)
            })
        value = {}

        value[month_fields[base_time.month-1]] = old_leave_balance
        while base_time.month < 12:
            start_time = base_time.replace(day=1)
            end_time = start_time + relativedelta(months=1, days=-1)
            leave_month = self.calculate_used_leave(emp, start_time, end_time)
            value[leave_used_fields[start_time.month-1]] = leave_month
            old_leave_balance = old_leave_balance + 1 - leave_month
            if base_time.month == 6 and old_leave_balance > 6:
                old_leave_balance = 7
            value[month_fields[start_time.month]] = old_leave_balance
            base_time = base_time + relativedelta(months=1)
        start_time = base_time.replace(day=1)
        end_time = start_time + relativedelta(months=1, days=-1)
        leave_month = self.calculate_used_leave(emp, start_time, end_time)
        value[leave_used_fields[start_time.month - 1]] = leave_month
        leave_record.write(value)
        return leave_record

    def calculate_total_leave_left(self, emp):
        now = datetime.now().date()
        base_time = emp.leave_milestone_date
        base_leave_balance = emp.leave_milestone
        old_leave_balance = base_leave_balance
        calculate_time = base_time
        while calculate_time.year < now.year - 1:
            leave_record = self.env['leave.left'].sudo().search([('employee_id', '=', emp.id),
                                                                 ('year', '=', calculate_time.year)])
            if leave_record:
                old_leave_balance = leave_record.th_12 + 1 - leave_record.leave_t12
            else:
                leave_record = self.init_leave_left(emp, calculate_time, old_leave_balance)
                old_leave_balance = leave_record.th_12 + 1 - leave_record.leave_t12
            calculate_time = (calculate_time + relativedelta(years=1)).replace(month=1, day=1)
        while calculate_time.year <= now.year:
            leave_record = self.init_leave_left(emp, calculate_time, old_leave_balance)
            old_leave_balance = leave_record.th_12 + 1 - leave_record.leave_t12
            calculate_time = (calculate_time + relativedelta(years=1)).replace(month=1, day=1)

    def re_calculate_leave_left(self, emp, start_date):
        month_fields = ['th_1', 'th_2', 'th_3', 'th_4', 'th_5', 'th_6', 'th_7',
                        'th_8', 'th_9', 'th_10', 'th_11', 'th_12']
        leave_used_fields = ['leave_t1', 'leave_t2', 'leave_t3', 'leave_t4', 'leave_t5', 'leave_t6', 'leave_t7',
                             'leave_t8', 'leave_t9', 'leave_t10', 'leave_t11', 'leave_t12']
        now = datetime.now().date()
        start_cal = (now + relativedelta(months=-3)).replace(day=1)
        if start_date >= start_cal:
            while start_cal.month <= now.month:
                end_cal = start_cal + relativedelta(months=1, days=-1)
                leave_used = self.calculate_used_leave(emp, start_cal, end_cal)
                leave_record = self.env['leave.left'].sudo().search([('employee_id', '=', emp.id),
                                                                    ('year', '=', start_cal.year)])
                if not leave_record:
                    self.calculate_total_leave_left(emp)
                    break
                else:
                    if leave_used != leave_record[leave_used_fields[start_cal.month-1]]:
                        new_leave_left = leave_record[month_fields[start_cal.month-1]] - leave_used + 1
                        if start_cal.month == 6 and new_leave_left > 6:
                            new_leave_left = 7
                        leave_record[month_fields[start_cal.month]] = new_leave_left
                        leave_record[leave_used_fields[start_cal.month-1]] = leave_used
                start_cal = start_cal + relativedelta(months=1)
        leave_left = self.env['leave.left'].sudo().search([('employee_id', '=', emp.id),
                                                           ('year', '=', start_date.year)])
        if not leave_left:
            self.calculate_total_leave_left(emp)
            leave_left = self.env['leave.left'].sudo().search([('employee_id', '=', emp.id),
                                                               ('year', '=', start_date.year)])
        report_leave_left = leave_left[month_fields[start_date.month - 1]]
        leave = leave_left[leave_used_fields[start_date.month - 1]]
        return report_leave_left, leave





















