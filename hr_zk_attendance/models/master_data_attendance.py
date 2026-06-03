from odoo import models, fields, api
from datetime import timedelta


class MasterDataAttendance(models.Model):
    _name = 'master.data.attendance'
    _description = 'Master Data Attendance'
    _order = 'employee_id, attendance_time DESC'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", compute="fill_department", store=True)
    attendance_time = fields.Datetime(string='Thời gian', required=True)
    attendance_type = fields.Char(string='Loại chấm công')
    month = fields.Integer("Tháng", compute="_get_month_data", store=True)

    @api.depends('attendance_time')
    def _get_month_data(self):
        for r in self:
            if r.attendance_time:
                r.month = r.attendance_time.month

    @api.depends('employee_id')
    def fill_department(self):
        for r in self:
            r.department_id = r.employee_id.department_id.id if r.employee_id.department_id.id else None

    def create(self, vals):
        rec = super().create(vals)
        if rec.employee_id and rec.attendance_time:
            self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                rec.employee_id,
                (rec.attendance_time + timedelta(hours=7)).date() - timedelta(days=1),
                (rec.attendance_time + timedelta(hours=7)).date() + timedelta(days=1)
            )
        return rec

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.employee_id:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    rec.employee_id,
                    (rec.attendance_time + timedelta(hours=7)).date() - timedelta(days=1),
                    (rec.attendance_time + timedelta(hours=7)).date() + timedelta(days=1)
                )
        return res

    def unlink(self):
        for rec in self:
            if rec.employee_id and rec.attendance_time:
                self.env['employee.attendance.v2'].sudo().recompute_for_employee(
                    rec.employee_id,
                    (rec.attendance_time + timedelta(hours=7)).date() - timedelta(days=1),
                    (rec.attendance_time + timedelta(hours=7)).date() + timedelta(days=1)
                )
        return super().unlink()
