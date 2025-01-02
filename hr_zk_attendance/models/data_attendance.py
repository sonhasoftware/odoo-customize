from odoo import models, fields, api


class DataAttendance(models.Model):
    _name = 'data.attendance'
    _description = 'Data Attendance'

    code = fields.Char("Mã chấm công")
    date_time = fields.Datetime("Ngày giờ")
    device_ip = fields.Char("Địa chỉ IP")

