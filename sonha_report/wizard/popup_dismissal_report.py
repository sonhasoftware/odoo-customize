from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class PopupDismissalReport(models.TransientModel):
    _name = 'popup.dismissal.report'

    from_date = fields.Date(string="Từ ngày", default=lambda self: self.default_from_date(), required=True)
    to_date = fields.Date(string="Đến ngày", default=lambda self: self.default_to_date(), required=True)
    type = fields.Selection([('dismissal', "Miễn nhiệm"), ('quit', "Nghỉ việc"), ('change', "Điều chuyển")], string="Loại", required=True)
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

    def action_confirm(self):
        self.env['dismissal.report'].search([]).sudo().unlink()
        list_records = self.env['dismissal.person'].sudo().search([('date_sign', '>=', self.from_date),
                                                                   ('date_sign', '<=', self.to_date)])
        if self.company_id:
            employee_record = self.env['employee.rel'].sudo().search([('person_dismissal', 'in', list_records.ids),
                                                                      ('name.company_id', '=', self.company_id.id)])
        if self.department_id and not self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.department.id == self.department_id.id)
        if self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.name.id == self.employee_id.id)
        if self.type and self.type == 'dismissal':
            employee_record = employee_record.filtered(lambda x: x.person_dismissal.form_discipline and "miễn nhiệm" in str(x.person_dismissal.form_discipline.name).lower())
        if self.type and self.type == 'quit':
            employee_record = employee_record.filtered(lambda x: x.person_dismissal.form_discipline and "chấm dứt hợp đồng" in str(x.person_dismissal.form_discipline.name).lower())
        if self.type and self.type == 'change':
            employee_record = employee_record.filtered(lambda x: x.person_dismissal.form_discipline and "điều chuyển" in str(x.person_dismissal.form_discipline.name).lower())
        if employee_record:
            for r in employee_record:
                vals = {
                    'person_discipline': r.name.name,
                    'reason': r.person_dismissal.reason,
                    'content': r.person_dismissal.content,
                    'discipline_number': r.person_dismissal.discipline_number,
                    'date_start': r.person_dismissal.date_start,
                    'date_sign': r.person_dismissal.date_sign,
                    'note': r.person_dismissal.note,
                    'sign_person': r.person_dismissal.sign_person.id,
                    'department_id': r.department.id,
                    'job_id': r.job.id,
                    'employee_code': r.emp_code,
                    'address': r.name.address_id.name,
                    'employee_id': r.name.id,
                }
                self.env['dismissal.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quyết định khác',
                'res_model': 'dismissal.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")

    def default_from_date(self):
        now = datetime.today().date()
        from_date = now.replace(day=1)
        return from_date

    def default_to_date(self):
        now = datetime.today().date()
        to_date = (now.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return to_date