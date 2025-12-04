from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class PopupRewardReport(models.TransientModel):
    _name = 'popup.reward.report'

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
        self.env['reward.report'].search([]).sudo().unlink()
        list_records = self.env['person.reward'].sudo().search([('sign_date', '>=', self.from_date),
                                                                ('sign_date', '<=', self.to_date)])
        if self.company_id:
            employee_record = self.env['employee.rel'].sudo().search([('person_reward', 'in', list_records.ids),
                                                                      ('name.company_id', '=', self.company_id.id)])
        if self.department_id and not self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.department.id == self.department_id.id)
        if self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.name.id == self.employee_id.id)

        if employee_record:
            for r in employee_record:
                vals = {
                    'object_reward': r.person_reward.object_reward.id,
                    'person_reward': r.name.name,
                    'title_reward': r.person_reward.title_reward.id,
                    'form_reward': r.person_reward.form_reward.id,
                    'level_reward': r.person_reward.level_reward.id,
                    'reason': r.person_reward.reason,
                    'amount': r.person_reward.amount,
                    'option': r.person_reward.option,
                    'note': r.person_reward.note,
                    'desision_number': r.person_reward.desision_number,
                    'state': r.person_reward.state.id,
                    'effective_date': r.person_reward.effective_date,
                    'sign_date': r.person_reward.sign_date,
                    'sign_person': r.person_reward.sign_person.id,
                    'person_reward_job': r.job.id,
                    'department_id': r.department.id,
                    'employee_code': r.emp_code,
                    'address': r.name.address_id.name,
                    'employee_id': r.name.id,
                }
                self.env['reward.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quyết định khen thưởng',
                'res_model': 'reward.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")