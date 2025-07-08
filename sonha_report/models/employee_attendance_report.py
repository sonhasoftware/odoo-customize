from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class EmployeeAttendanceReport(models.Model):
    _name = 'employee.attendance.report'

    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    weekday = fields.Selection([('0', "Thứ hai"),
                                ('1', "Thứ ba"),
                                ('2', "Thứ tư"),
                                ('3', "Thứ năm"),
                                ('4', "Thứ 6"),
                                ('5', "Thứ 7"),
                                ('6', "Chủ Nhật")], string="Thứ")
    date = fields.Date(string="Ngày")
    check_in = fields.Datetime(string="Giờ vào")
    check_out = fields.Datetime(string="Giờ ra")
    shift = fields.Many2one('config.shift', string="Ca làm việc")
    note = fields.Selection([('no_in', "Không có check in"),
                             ('no_out', "Không có check out"),
                             ('no_shift', "Không có ca làm việc")],
                            string="Ghi chú",)
    minutes_late = fields.Float("Số phút đi muộn")
    minutes_early = fields.Float("Số phút về sớm")
    over_time = fields.Float("Giờ làm thêm")
    leave = fields.Float("Nghỉ phép")
    compensatory = fields.Float("Nghỉ bù")
    work_day = fields.Float("Ngày công")
    over_time_nb = fields.Float("Làm thêm hưởng NB")

