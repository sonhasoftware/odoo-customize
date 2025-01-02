from odoo import models, fields, api


class WizardDateRange(models.TransientModel):
    _name = 'wizard.date.range'
    _description = 'Wizard for Selecting Date Range'

    company_id = fields.Many2one('res.company', string="Công ty")
    start_date = fields.Date(string="Ngày bắt đầu", required=True)
    end_date = fields.Date(string="Ngày kết thúc", required=True)

    def action_apply(self):
        list_attendances = self.env['employee.attendance'].sudo().search([
            ('date', '>=', self.start_date),
            ('date', '<=', self.end_date),
            ('employee_id.company_id', '=', self.company_id.id)
        ])
        model = self.env['employee.attendance.store']
        for record in list_attendances:
            existing_record = model.sudo().search([
                ('employee_id', '=', record.employee_id.id),
                ('date', '=', record.date)
            ], limit=1)
            vals = {
                'department_id': record.department_id.id,
                'weekday': record.weekday,
                'check_in': record.check_in,
                'check_out': record.check_out,
                'duration': record.duration,
                'shift': record.shift.id if record.shift else False,
                'time_check_in': record.time_check_in,
                'time_check_out': record.time_check_out,
                'check_no_in': record.check_no_in,
                'check_no_out': record.check_no_out,
                'note': record.note,
                'work_day': record.work_day,
                'minutes_late': record.minutes_late,
                'minutes_early': record.minutes_early,
                'month': record.month,
                'year': record.year,
                'over_time': record.over_time,
                'leave': record.leave,
                'compensatory': record.compensatory,
                'public_leave': record.public_leave,
                'c2k3': record.c2k3,
                'c3k4': record.c3k4,
            }

            if existing_record:
                # Cập nhật từng trường để đảm bảo lưu dữ liệu
                for field, value in vals.items():
                    existing_record.sudo().write({field: value})
            else:
                # Tạo mới nếu không tồn tại
                vals.update({
                    'employee_id': record.employee_id.id,
                    'date': record.date,
                })
                model.sudo().create(vals)
