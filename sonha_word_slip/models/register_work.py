from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from datetime import datetime, time, timedelta, date
from odoo.exceptions import UserError, ValidationError


class RegisterWork(models.Model):
    _name = 'register.work'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.model
    def _default_department(self):
        # Lấy phòng ban từ user đang đăng nhập
        user = self.env.user
        if user.employee_id and user.employee_id.department_id:
            return user.employee_id.department_id.id
        return False

    employee_id = fields.Many2many('hr.employee', 'register_work_rel',
                                   'register_work', 'register_work_id',
                                   string="Tên nhân viên", tracking=True, required=True)
    shift = fields.Many2one('config.shift', string="Ca", tracking=True, required=True)
    start_date = fields.Date("Từ ngày", tracking=True, required=True)
    end_date = fields.Date("Đến ngày", tracking=True, required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True, tracking=True, default=lambda self: self._default_department())
    company_id = fields.Many2one('res.company', string="Công ty", required=True, default=lambda self: self.env.company)

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
            self.sudo().create_distribute_shift(record)
            record.explore_to_work()
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
                self.env['distribute.shift'].sudo().create(vals)
                temp_date = temp_date + timedelta(days=1)

    @api.constrains('start_date', 'end_date')
    def _check_validity(self):
        for r in self:
            day = self.env['res.company'].sudo().search([('id', '=', r.employee_id.company_id.id)], limit=1)
            if r.employee_id and day and day.shift != 0:
                now = date.today()
                date_valid = now - timedelta(days=day.shift)
                if r.start_date < date_valid or r.end_date < date_valid:
                    raise ValidationError("Bạn không thể đăng ký ca cho ngày quá khứ")

    @api.constrains('employee_id', 'start_date', 'end_date')
    def _check_overlap(self):
        for record in self:
            for employee in record.employee_id:
                overlapping_records = self.env['register.work'].sudo().search([
                    ('id', '!=', record.id),  # Bỏ qua bản ghi hiện tại
                    ('employee_id', 'in', employee.id),  # Nhân viên đã đăng ký
                    '|',
                    '&', ('start_date', '<=', record.end_date), ('end_date', '>=', record.start_date),
                    # Trùng hoặc gối ngày
                    '&', ('start_date', '<=', record.start_date), ('end_date', '>=', record.end_date)
                    # Bao trùm hoàn toàn
                ])

                if overlapping_records:
                    raise ValidationError(
                        f"Nhân viên {employee.name} đã có ca trong thời gian bạn chọn. Vui lòng chọn khoảng thời gian khác.")

    def explore_to_work(self):
        model = self.env['rel.ca'].sudo()

        if not self.employee_id or not self.start_date or not self.end_date:
            return

        model.search([('key_form', '=', self.id)]).unlink()

        current_date = self.start_date
        while current_date <= self.end_date:
            for emp in self.employee_id:
                model.create({
                    'employee_id': emp.id,
                    'department_id': self.department_id.id,
                    'company_id': self.company_id.id,
                    'date': current_date,
                    'shift_id': self.shift.id,
                    'key_form': self.id,
                    'type': 'dang_ky_ca'
                })
            current_date += timedelta(days=1)

    def write(self, vals):
        res = super(RegisterWork, self).write(vals)
        for rec in self:
            rec.explore_to_work()
        return res

    def unlink(self):
        for r in self:
            self.env['rel.ca'].sudo().search([('key_form', '=', r.id)]).unlink()
        return super(RegisterWork, self).unlink()


