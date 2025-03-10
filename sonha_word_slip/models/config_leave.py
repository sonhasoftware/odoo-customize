from odoo import api, fields, models


class ConfigLeave(models.Model):
    _name = 'config.leave'

    employee_ids = fields.Many2many('hr.employee', 'ir_employee_leave_rel',
                                    'employee_leave_rel', 'leave_rel',
                                    string='Tên nhân viên', required=True)
    word_slip = fields.Many2one('config.word.slip', required=True, string="Loại nghỉ")
    date = fields.Integer("Ngày tối đa", default=0)
