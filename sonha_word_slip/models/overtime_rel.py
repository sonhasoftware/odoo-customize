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
    percent = fields.Selection([('100', "100%"),
                                ('150', "150%"),
                                ('200', "200%"),
                                ('270', "270%"),
                                ('300', "300%"),
                                ('390', "390%")],
                               string="Phần trăm hưởng", default="100", compute="get_percent_ot")

    @api.depends('overtime_id', 'overtime_id.department_id')
    def get_percent_ot(self):
        for r in self:
            leave = self.env['resource.calendar.leaves'].sudo().search([])
            leave = leave.filtered(lambda x: x.date_from.date() <= r.date <= x.date_to.date())
            p = self.env['config.overtime'].sudo().search([('department_id', '=', r.overtime_id.department_id.id)])
            weekday = r.date.weekday()
            if leave:
                r.percent = '300'
            elif weekday == 6:
                r.percent = '200'
            elif p:
                r.percent = p.percent
            else:
                r.percent = '100'

    @api.constrains("date", "start_time", "end_time", "overtime_id")
    def validate_overtime(self):
        for record in self:
            if record.end_time < record.start_time:
                raise ValidationError("Thời gian kết thúc không được bé hơn thời gian bắt đầu!")
            if record.start_time >= 24:
                start_hours = 0
            else:
                start_hours = record.start_time

            if record.end_time >= 24:
                end_hours = 0
            else:
                end_hours = record.end_time

            hours_start = int(start_hours)
            minutes_start = int(round((start_hours - hours_start) * 60))
            time_start = time(hour=hours_start, minute=minutes_start)
            hours_end = int(end_hours)
            minutes_end = int(round((end_hours - hours_end) * 60))
            time_end = time(hour=hours_end, minute=minutes_end)
            list_employee = [
                record.overtime_id.employee_id.id] if record.overtime_id.employee_id else record.overtime_id.employee_ids.ids
            for employee in list_employee:
                data = self.env['employee.attendance.v2'].sudo().search([
                    ('date', '=', record.date),
                    ('employee_id', '=', employee)])
                check_in_out = self.env['master.data.attendance'].sudo().search([
                    ('employee_id', '=', employee)])
                check_in_out = check_in_out.filtered(lambda x: (x.attendance_time + relativedelta(hours=7)).date() == record.date)
                not_check_in_out = data.filtered(lambda x: (x.check_in and x.check_in.date() == record.date) or (x.check_out and x.check_out.date() == record.date))
                shift = data.shift
                if not shift:
                    raise ValidationError("Không thể tạo bản ghi khi bạn chưa có ca làm việc")
                if not check_in_out and not not_check_in_out:
                    raise ValidationError("Không thể tạo bản ghi do không có dữ liệu check_in check_out!")
                start_shift = (shift.start + relativedelta(hours=7)).time()
                start_noon_shift = shift.from_rest if shift.from_rest else False
                if start_noon_shift:
                    start_noon_shift = (shift.from_rest + relativedelta(hours=7)).time()
                end_shift = (shift.end_shift + relativedelta(hours=7)).time()
                end_noon_shift = shift.to_rest if shift.to_rest else False
                if end_noon_shift:
                    end_noon_shift = (shift.to_rest + relativedelta(hours=7)).time()

                if not shift.shift_ot:
                    def is_overlap(start1, end1, start2, end2):
                        return start1 < end2 and end1 > start2

                    if start_noon_shift and end_noon_shift:
                        if (
                                is_overlap(time_start, time_end, start_shift, start_noon_shift) or
                                is_overlap(time_start, time_end, end_noon_shift, end_shift)
                        ):
                            raise ValidationError(
                                "Khoảng thời gian bạn đăng ký đã nằm trong thời gian làm việc của ca!")
                    else:
                        # Không có nghỉ trưa, ca làm liền mạch
                        if is_overlap(time_start, time_end, start_shift, end_shift):
                            raise ValidationError(
                                "Khoảng thời gian bạn đăng ký đã nằm trong thời gian làm việc của ca!")
                # else:
                #     def is_inside(start1, end1, start2, end2):
                #         return start1 >= start2 and end1 <= end2
                #
                #     if start_noon_shift and end_noon_shift:
                #         # Có phân tách giữa ca sáng và chiều (loại trừ giờ nghỉ trưa)
                #         valid = (
                #                 is_inside(time_start, time_end, start_shift, start_noon_shift) or
                #                 is_inside(time_start, time_end, end_noon_shift, end_shift)
                #         )
                #     else:
                #         # Không có giờ nghỉ trưa → dùng mốc 08:00 – 17:00
                #         valid = is_inside(time_start, time_end, start_shift, end_shift)
                #
                #     if not valid:
                #         raise ValidationError("Chỉ được phép đăng ký trong khoảng thời gian của ca")

    def unlink(self):
        for r in self:
            self.env['rel.lam.them'].sudo().search([('key', '=', r.id)]).unlink()
        return super(OvertimeRel, self).unlink()
