from odoo import api, fields, models

class EmployeeShiftReport(models.Model):
    _name = 'employee.shift.report'


    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    employee_code = fields.Char(string="Mã nhân viên")
    weekday = fields.Selection([('0', "Thứ hai"),
                                ('1', "Thứ ba"),
                                ('2', "Thứ tư"),
                                ('3', "Thứ năm"),
                                ('4', "Thứ 6"),
                                ('5', "Thứ 7"),
                                ('6', "Chủ Nhật")], string="Thứ")
    date = fields.Date(string="Ngày")
    shift = fields.Many2one('config.shift', string="Ca làm việc")
