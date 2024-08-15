from odoo import api, fields, models


class RegisterWork(models.Model):
    _name = 'register.work'

    employee_id = fields.Many2many('hr.employee', 'register_work_rel',
                                   'register_work', 'register_work_id',
                                   string="Tên nhân viên")
    shift = fields.Many2one('config.shift', string="Ca")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
