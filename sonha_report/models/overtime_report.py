from odoo import models, fields, api


class OvertimeReport(models.Model):
    _name = 'overtime.report'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    create_emp = fields.Many2one('res.users', string="Người tạo")
    employee_ids = fields.Many2many('hr.employee', 'overtime_report_hr_employee_rel',
                                    'overtime_report_id', 'employee_id', string="Tên nhân viên")
    overtime_create_date = fields.Datetime("Ngày tạo")
    type = fields.Selection([('one', "Tạo cho tôi"),
                             ('many', "Tạo hộ")], string="Loại đăng ký")
    all_time = fields.Text("Thời gian")
    status = fields.Selection([('draft', "Chờ duyệt"),
                               ('done', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái")
