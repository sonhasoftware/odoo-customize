from odoo import models, fields, api


class RelCa(models.Model):
    _name = 'rel.ca'

    employee_id = fields.Many2one('hr.employee', string="Tên nhân viên", store=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", store=True)
    company_id = fields.Many2one('res.company', string="Công ty", store=True)
    date = fields.Date(string="Ngày", store=True)
    shift_id = fields.Many2one('config.shift', string="Ca", store=True)

    key = fields.Many2one('register.shift.rel', string="Key ngày", store=True)
    key_register_shift = fields.Many2one('register.shift', string="Key đổi ca", store=True)
    key_register_work = fields.Many2one('register.work', string="Key đăng ký ca", store=True)
