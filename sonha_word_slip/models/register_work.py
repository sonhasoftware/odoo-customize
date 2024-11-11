from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta


class RegisterWork(models.Model):
    _name = 'register.work'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    employee_id = fields.Many2many('hr.employee', 'register_work_rel',
                                   'register_work', 'register_work_id',
                                   string="Tên nhân viên", tracking=True)
    shift = fields.Many2one('config.shift', string="Ca", tracking=True)
    start_date = fields.Date("Từ ngày", tracking=True)
    end_date = fields.Date("Đến ngày", tracking=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True)

    #Chỉ hiển thị các nhân viên trong phòng ban đã chọn
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


    def create(self, vals):
        list_record = super(RegisterWork, self).create(vals)
        for record in list_record:
            self.create_distribute_shift(record)
        return list_record

    def create_distribute_shift(self, record):
        for emp in record.employee_id:
            temp_date = record.start_date
            while temp_date <= record.end_date:
                emp_id = emp.id
                vals = {
                    'employee_id': emp_id or '',
                    'date': temp_date or '',
                    'shift': record.shift.id or '',
                }
                self.env['distribute.shift'].create(vals)
                temp_date = temp_date + timedelta(days=1)

