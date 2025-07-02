from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time
from dateutil.relativedelta import relativedelta


class OvertimeRel(models.Model):
    _name = 'overtime.rel'

    date = fields.Date("Ngày", required=True)
    start_time = fields.Float("Thời gian bắt đầu", required=True)
    end_time = fields.Float("Thời gian kết thúc", required=True)
    coefficient = fields.Float("Hệ số", default=1)
    overtime_id = fields.Many2one('register.overtime.update')

    @api.constrains("date", "start_time", "end_time", "overtime_id")
    def validate_overtime(self):
        for record in self:
            hours_start = int(record.start_time)
            minutes_start = int(round((record.start_time - hours_start) * 60))
            time_start = time(hour=hours_start, minute=minutes_start)
            hours_end = int(record.end_time)
            minutes_end = int(round((record.end_time - hours_end) * 60))
            time_end = time(hour=hours_end, minute=minutes_end)
            list_employee = [record.overtime_id.employee_id.id] if record.overtime_id.employee_id else record.overtime_id.employee_ids.ids
            for employee in list_employee:
                data = self.env['employee.attendance'].sudo().search([
                    ('date', '=', record.date),
                    ('employee_id', '=', employee)])
                shift = data.shift
                check_in = data.check_in
                check_out = data.check_out
                if not shift:
                    raise ValidationError("Không thể tạo bản ghi khi bạn chưa có ca làm việc")
                if not check_in and not check_out:
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
                else:
                    def is_inside(start1, end1, start2, end2):
                        return start1 >= start2 and end1 <= end2

                    if start_noon_shift and end_noon_shift:
                        # Có phân tách giữa ca sáng và chiều (loại trừ giờ nghỉ trưa)
                        valid = (
                                is_inside(time_start, time_end, start_shift, start_noon_shift) or
                                is_inside(time_start, time_end, end_noon_shift, end_shift)
                        )
                    else:
                        # Không có giờ nghỉ trưa → dùng mốc 08:00 – 17:00
                        valid = is_inside(time_start, time_end, start_shift, end_shift)

                    if not valid:
                        raise ValidationError("Chỉ được phép đăng ký trong khoảng thời gian của ca")
