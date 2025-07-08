from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupEmployeeAttendanceReport(models.TransientModel):
    _name = 'popup.employee.attendance.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")


    def action_confirm(self):
        self.env['employee.attendance.report'].search([]).sudo().unlink()
        list_records = self.env['employee.attendance'].sudo().search([('date', '>=', self.from_date),
                                                                      ('date', '<=', self.to_date)])
        if self.company_id and not self.department_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
        if self.department_id and not self.employee_id:
            list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.employee_id:
            list_records = list_records.filtered(lambda x: x.employee_id.id == self.employee_id.id)
        if list_records:
            for r in list_records:
                vals = {
                    'employee_id': r.employee_id.id,
                    'department_id': r.department_id.id,
                    'weekday': r.weekday,
                    'date': r.date,
                    'check_in': r.check_in,
                    'check_out': r.check_out,
                    'shift': r.shift.id,
                    'note': r.note,
                    'minutes_late': r.minutes_late,
                    'minutes_early': r.minutes_early,
                    'work_day': r.work_day,
                    'over_time': r.over_time,
                    'leave': r.leave,
                    'compensatory': r.compensatory,
                    'over_time_nb': r.over_time_nb,
                }
                self.env['employee.attendance.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo công chi tiết',
                'res_model': 'employee.attendance.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")

