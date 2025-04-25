from odoo import models, api, fields


class DismissalReport(models.Model):
    _name = 'dismissal.report'

    person_discipline = fields.Char(string="Nhân viên")
    reason = fields.Char(string="Lý do")
    content = fields.Char(string="Nội dung")
    discipline_number = fields.Char(string="Số quyết định")
    date_start = fields.Date("Ngày hiệu lực")
    date_sign = fields.Date(string="Ngày ký")
    note = fields.Char(string="Chú thích")
    sign_person = fields.Many2one('hr.employee', string="Người phê duyệt")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    employee_code = fields.Char(string="Mã nhân viên")

