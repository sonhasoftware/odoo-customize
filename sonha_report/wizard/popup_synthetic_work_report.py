from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class PopupSyntheticWorkReport(models.TransientModel):
    _name = 'popup.synthetic.work.report'

    from_date = fields.Date(string="Từ ngày", default=lambda self: self.default_from_date(), required=True)
    to_date = fields.Date(string="Đến ngày", default=lambda self: self.default_to_date(), required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị",
                                 domain="[('id', 'in', allowed_company_ids)]",
                                 default=lambda self: self.env.user.company_id, required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    default=lambda self: self.default_department())
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  default=lambda self: self.default_employee_id())
    department_domain = fields.Binary(compute="_compute_department_domain")
    employee_domain = fields.Binary(compute="_compute_employee_domain")

    def default_employee_id(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        if emp and not (self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                'sonha_employee.group_back_up_employee')):
            return emp
        else:
            return None

    def default_department(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        department_id = emp.department_id
        if department_id:
            return department_id
        else:
            return None

    @api.onchange("company_id")
    def _compute_department_domain(self):
        for rec in self:
            domain = [
                ('company_id', 'in', self.env.user.company_ids.ids),
                '|',
                ('manager_id.user_id', '=', self.env.user.id),
                ('id', '=', self.env.user.employee_id.department_id.id)
            ]
            if self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                    'sonha_employee.group_back_up_employee'):
                domain = [('company_id', 'in', self.env.user.company_ids.ids)]
            if rec.company_id:
                domain.append(("company_id", "=", rec.company_id.id))
            rec.department_domain = domain

    @api.onchange("company_id", "department_id")
    def _compute_employee_domain(self):
        for rec in self:
            domain = [('company_id', 'in', self.env.user.company_ids.ids),
                      ('id', 'child_of', self.env.user.employee_id.id)]
            if self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                    'sonha_employee.group_back_up_employee'):
                domain = [('company_id', 'in', self.env.user.company_ids.ids)]
            if rec.department_id:
                domain.append(("department_id", "=", rec.department_id.id))
            if rec.company_id:
                domain.append(("company_id", "=", rec.company_id.id))
            rec.employee_domain = domain

    def default_from_date(self):
        now = datetime.today().date()
        from_date = now.replace(day=1)
        return from_date

    def default_to_date(self):
        now = datetime.today().date()
        to_date = (now.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return to_date


    def action_confirm(self):
        self.env['synthetic.work.report'].search([]).sudo().unlink()
        list_records = self.env['synthetic.work'].sudo().search([('start_date', '=', self.from_date),
                                                                 ('end_date', '=', self.to_date)])
        if self.company_id and not self.department_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
        if self.department_id and not self.employee_id:
            list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.employee_id:
            list_records = list_records.filtered(lambda x: x.employee_id.id == self.employee_id.id)
        if list_records:
            for r in list_records:
                vals = {
                    'employee_id': r.employee_id.id,
                    'department_id': r.department_id.id,
                    'employee_code': r.employee_code,
                    'date_work': r.date_work,
                    'apprenticeship': r.apprenticeship,
                    'probationary_period': r.probationary_period,
                    'ot_one_hundred': r.ot_one_hundred,
                    'ot_one_hundred_fifty': r.ot_one_hundred_fifty,
                    'ot_three_hundred': r.ot_three_hundred,
                    'paid_leave': r.paid_leave,
                    'number_minutes_late': r.number_minutes_late,
                    'number_minutes_early': r.number_minutes_early,
                    'shift_two_crew_three': r.shift_two_crew_three,
                    'shift_three_crew_four': r.shift_three_crew_four,
                    'on_leave': r.on_leave,
                    'compensatory_leave': r.compensatory_leave,
                    'filial_leave': r.filial_leave,
                    'grandparents_leave': r.grandparents_leave,
                    'vacation': r.vacation,
                    'public_leave': r.public_leave,
                    'total_work': r.total_work,
                    'month': r.month,
                    'hours_reinforcement': r.hours_reinforcement,
                }
                self.env['synthetic.work.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo công tổng hợp',
                'res_model': 'synthetic.work.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")

