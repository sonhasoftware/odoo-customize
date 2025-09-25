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
        self.env['leave.report'].search([]).sudo().unlink()
        list_records = self.env['employee.attendance'].sudo().search([('date', '>=', self.from_date),
                                                                      ('date', '<=', self.to_date)])
        if self.company_id and not self.department_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
        if self.department_id and not self.employee_id:
            list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.employee_id:
            list_records = list_records.filtered(lambda x: x.employee_id.id == self.employee_id.id)
        list_records = list_records.filtered(lambda x: x.leave != 0)
        if list_records:
            eliminated_employee = []
            list_employee = list_records.employee_id
            for emp in list_employee:
                if emp.leave_milestone_date and self.from_date >= emp.leave_milestone_date:
                    # old_leave_left = self.caculate_begin_period(emp)
                    old_leave_left, total_leave = self.env['popup.synthetic.leave.report'].re_calculate_leave_left(emp, self.from_date)
                    if self.from_date.day != 1:
                        start_date = self.from_date.replace(day=1)
                        end_date = self.from_date + relativedelta(days=-1)
                        used_leave = self.env['popup.synthetic.leave.report'].calculate_used_leave(emp, start_date, end_date)
                        old_leave_left = old_leave_left - used_leave
                    employee_record = list_records.filtered(lambda x: x.employee_id.id == emp.id)
                    for rec in employee_record:
                        new_leave_left = old_leave_left - rec.leave
                        vals = {
                            'employee_id': rec.employee_id.id,
                            'department_id': rec.department_id.id,
                            'begin_period': old_leave_left,
                            'leave': rec.leave,
                            'date': rec.date,
                            'total_leave_left': new_leave_left,
                        }
                        self.env['leave.report'].sudo().create(vals)
                        old_leave_left = new_leave_left
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
                'name': 'Báo cáo phép chi tiết',
                'res_model': 'leave.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Nhân viên không sử dụng phép trong tháng này!")











