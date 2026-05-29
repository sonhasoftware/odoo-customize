from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta


class OvertimeRel(models.Model):
    _name = 'overtime.rel'

    date = fields.Date("Ngày", required=True)
    start_time = fields.Float("Thời gian bắt đầu", required=True)
    end_time = fields.Float("Thời gian kết thúc", required=True)
    coefficient = fields.Float("Hệ số", default=1)
    overtime_id = fields.Many2one('register.overtime.update')
    reason = fields.Char("Lý do")

    @api.constrains("date", "start_time", "end_time", "overtime_id")
    def validate_overtime(self):
        Attendance = self.env['employee.attendance.v2'].sudo()
        for record in self:
            if record.end_time < record.start_time:
                raise ValidationError("Thời gian kết thúc không được bé hơn thời gian bắt đầu!")
            list_employee = [
                record.overtime_id.employee_id.id] if record.overtime_id.employee_id else record.overtime_id.employee_ids.ids
            ot_start, ot_end = Attendance._get_overtime_line_interval_local(record)
            for employee_id in list_employee:
                employee = self.env['hr.employee'].sudo().browse(employee_id)
                owner = Attendance._get_overtime_owner_record(record, employee)
                if not owner or not owner.shift:
                    raise ValidationError("Không thể tạo bản ghi khi bạn chưa có ca làm việc")
                if not owner.shift.shift_ot:
                    shift_start, shift_end = Attendance._get_shift_interval_local(owner)
                    overlap_start, overlap_end = Attendance._intersect_interval(ot_start, ot_end, shift_start, shift_end)
                    if overlap_start and overlap_end:
                        raise ValidationError(
                            "Khoảng thời gian bạn đăng ký đã nằm trong thời gian làm việc của ca!")

    def unlink(self):
        for r in self:
            self.env['rel.lam.them'].sudo().search([('key', '=', r.id)]).unlink()
        return super(OvertimeRel, self).unlink()
