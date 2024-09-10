from odoo import api, fields, models


class RegisterWork(models.Model):
    _name = 'register.work'

    employee_id = fields.Many2many('hr.employee', 'register_work_rel',
                                   'register_work', 'register_work_id',
                                   string="Tên nhân viên")
    shift = fields.Many2one('config.shift', string="Ca")
    start_date = fields.Date("Từ ngày")
    end_date = fields.Date("Đến ngày")
    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)

    @api.onchange('department_id')
    def _onchange_department_id(self):
        for r in self:
            if r.department_id:
                return {
                    'domain': {
                        'employee_id': [('department_id', '=', self.department_id.id)]
                    }
                }
            else:
                return {
                    'domain': {
                        'employee_id': []
                    }
                }
