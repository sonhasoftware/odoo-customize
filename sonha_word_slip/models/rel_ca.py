from odoo import models, fields, api


class RelCa(models.Model):
    _name = 'rel.ca'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)
    company_id = fields.Many2one('res.company', string="Công ty", store=True)
    date = fields.Date(string="Ngày", store=True)
    shift_id = fields.Many2one('config.shift', string="Ca", store=True)

    key = fields.Many2one('register.shift.rel', string="Key ngày", store=True)
    key_form = fields.Integer(string="Key ca", store=True)
    type = fields.Selection([('dang_ky_ca', "Đăng ký ca"),
                             ('doi_ca', "Đổi ca")], string="Loại", store=True)
