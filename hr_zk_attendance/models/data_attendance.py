import datetime

from odoo import models, fields, api
from datetime import timedelta
from dateutil.relativedelta import relativedelta


class DataAttendance(models.Model):
    _name = 'data.attendance'
    _description = 'Data Attendance'

    code = fields.Char("Mã chấm công")
    date_time = fields.Datetime("Ngày giờ")
    device_ip = fields.Char("Địa chỉ IP")

    def clone_attendance_data(self):
        self.clone_data_mcc_old()
        # today = fields.Datetime.now()  # Lấy thời gian hiện tại
        # first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0)  # Ngày đầu tháng, reset giờ về 00:00:00
        # first_day_last_month = first_day_this_month - relativedelta(months=1)  # Ngày đầu tháng trước
        #
        # # Lấy ngày đầu tháng sau để làm mốc cho "<"
        # first_day_next_month = first_day_this_month + relativedelta(months=1)
        #
        # # Tạo domain tìm kiếm
        # domain = [
        #     ('date_time', '>=', first_day_last_month),  # Từ ngày đầu tháng trước
        #     ('date_time', '<', first_day_next_month)  # Đến trước ngày đầu tháng sau
        # ]
        # attendance_records = self.sudo().search(domain)
        # employee_model = self.env['hr.employee']
        # master_attendance_model = self.env['master.data.attendance']
        #
        # for record in attendance_records:
        #     # Tìm nhân viên dựa vào mã chấm công
        #     employee = employee_model.sudo().search([('device_id_num', '=', record.code)])
        #     if employee:
        #         # Kiểm tra xem bản ghi đã tồn tại trong master.data.attendance chưa
        #         existing_record = master_attendance_model.sudo().search([
        #             ('employee_id', '=', employee.id),
        #             ('attendance_time', '=', record.date_time - timedelta(hours=7))
        #         ], limit=1)
        #
        #         if not existing_record:
        #             # Tạo bản ghi mới trong bảng master.data.attendance
        #             master_attendance_model.create({
        #                 'employee_id': employee.id,
        #                 'attendance_time': record.date_time - timedelta(hours=7),
        #             })

    def clone_data_mcc_old(self):
        today = datetime.datetime.now()
        if today.day <= 10:
            start_date = today + timedelta(days=-10)
        else:
            start_date = today.replace(
                day=1
            )
        end_date = today.replace(day=1) + relativedelta(months=1)

        start_date_text = start_date.strftime('%d/%m/%Y')
        end_date_text = end_date.strftime('%d/%m/%Y')

        self.env.cr.execute(
            "CALL PR_DL_MCC_OLD(%s, %s);",
            (start_date_text, end_date_text)
        )
        return True

        # attendance_records = self.sudo().search([
        #     ('date_time', '>=', start_date),
        #     ('date_time', '<=', end_date)
        # ], order='date_time')
        # employee_model = self.env['hr.employee']
        # master_attendance_model = self.env['master.data.attendance']
        #
        # for record in attendance_records:
        #     # Tìm nhân viên dựa vào mã chấm công
        #     employee = employee_model.sudo().search([('device_id_num', '=', record.code)], limit=1)
        #     if employee:
        #         # Kiểm tra xem bản ghi đã tồn tại trong master.data.attendance chưa
        #         existing_record = master_attendance_model.sudo().search([
        #             ('employee_id', '=', employee.id),
        #             ('attendance_time', '=', record.date_time - timedelta(hours=7))
        #         ], limit=1)
        #
        #         if not existing_record:
        #             # Tạo bản ghi mới trong bảng master.data.attendance
        #             master_attendance_model.create({
        #                 'employee_id': employee.id,
        #                 'attendance_time': record.date_time - timedelta(hours=7),
        #             })
