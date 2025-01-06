from odoo import models, fields, api
from datetime import timedelta


class DataAttendance(models.Model):
    _name = 'data.attendance'
    _description = 'Data Attendance'

    code = fields.Char("Mã chấm công")
    date_time = fields.Datetime("Ngày giờ")
    device_ip = fields.Char("Địa chỉ IP")

    def clone_attendance_data(self):
        attendance_records = self.sudo().search([])
        employee_model = self.env['hr.employee']
        master_attendance_model = self.env['master.data.attendance']

        for record in attendance_records:
            # Tìm nhân viên dựa vào mã chấm công
            employee = employee_model.sudo().search([('device_id_num', '=', record.code)])
            if employee:
                # Kiểm tra xem bản ghi đã tồn tại trong master.data.attendance chưa
                existing_record = master_attendance_model.sudo().search([
                    ('employee_id', '=', employee.id),
                    ('attendance_time', '=', record.date_time)
                ], limit=1)

                if not existing_record:
                    # Tạo bản ghi mới trong bảng master.data.attendance
                    master_attendance_model.create({
                        'employee_id': employee.id,
                        'attendance_time': record.date_time - timedelta(hours=7),
                    })
