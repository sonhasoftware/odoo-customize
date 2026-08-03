from odoo import models, fields, api
from datetime import timedelta


def _attendance_v2_date_window(attendance_time):
    local_date = (attendance_time + timedelta(hours=7)).date()
    return local_date - timedelta(days=1), local_date + timedelta(days=1)


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

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._recompute_attendance_v2_for_punches()
        return recs

    def write(self, vals):
        old_punches = self._get_attendance_v2_recompute_payload()
        res = super().write(vals)
        self._recompute_attendance_v2_payload(old_punches)
        self._recompute_attendance_v2_for_punches()
        return res

    def unlink(self):
        old_punches = self._get_attendance_v2_recompute_payload()
        res = super().unlink()
        self._recompute_attendance_v2_payload(old_punches)
        return res

    def _get_attendance_v2_recompute_payload(self):
        payload = []
        for rec in self:
            if rec.employee_id and rec.attendance_time:
                payload.append((rec.employee_id.id, rec.attendance_time))
        return payload

    def _recompute_attendance_v2_for_punches(self):
        self._recompute_attendance_v2_payload(self._get_attendance_v2_recompute_payload())

    def _recompute_attendance_v2_payload(self, payload):
        attendance_v2 = self.env['employee.attendance.v2'].sudo()
        for employee_id, attendance_time in payload:
            date_from, date_to = _attendance_v2_date_window(attendance_time)
            attendance_v2.recompute_for_employee(employee_id, date_from, date_to)
