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
        self.with_delay().clone_data_mcc_old()

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

        self.env.cr.execute("""
                SELECT DISTINCT
                    a.id
                FROM employee_attendance_v2 a
                INNER JOIN attendance_calculation c
                    ON c.employee_id = a.employee_id
                    AND c.date = a.date
                WHERE c.cal = FALSE
                ORDER BY a.id
            """)

        attendance_ids = [
            row[0]
            for row in self.env.cr.fetchall()
        ]

        if not attendance_ids:
            return True

        batch_size = 120

        for i in range(0, len(attendance_ids), batch_size):
            batch_ids = attendance_ids[i:i + batch_size]

            self.with_delay(
                description=f'Recompute attendance batch {i // batch_size + 1}')._recompute_attendance_batch(batch_ids)

        return True

    def _recompute_attendance_batch(self, attendance_ids):
        Attendance = self.env['employee.attendance.v2']

        records = Attendance.browse(attendance_ids).exists()

        for record in records:
            record._recompute_attendance_v2_fields()

        # Đánh dấu các dòng calculation đã xử lý
        for record in records:
            self.env.cr.execute("""
                    UPDATE attendance_calculation
                    SET cal = TRUE
                    WHERE employee_id = %s
                      AND date = %s
                      AND cal = FALSE
                """, (
                record.employee_id.id,
                record.date,
            ))

        return True

        # today = fields.Datetime.now()
        #
        # start_date = (today - timedelta(days=6)).replace(
        #     hour=0,
        #     minute=0,
        #     second=0,
        #     microsecond=0
        # )
        #
        # end_date = today.replace(
        #     hour=23,
        #     minute=59,
        #     second=59,
        #     microsecond=999999
        # )
        #
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
