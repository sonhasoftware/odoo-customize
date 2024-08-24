from odoo import models, fields
import datetime


class Timesheet(models.TransientModel):
    _name = 'timesheet'

    department = fields.Many2one('hr.department', string="Phòng ban")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")

    def action_confirm(self):
        list_emp = self.env['hr.employee'].sudo().search([('department_id', '=', self.department.id)])
        for emp in list_emp:
            data_attendance = self.env['employee.attendance'].sudo().search([('employee_id', '=', emp.id)])
            duration = sum(data_attendance.duration)
            vals = {
                'employee_id': emp.id,
                'date_work': duration,
                'apprenticeship': 0,

            }
            self.env['synthetic.work'].sudo().create(vals)

