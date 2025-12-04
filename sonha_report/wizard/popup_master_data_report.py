from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class PopupMasterDataReport(models.TransientModel):
    _name = 'popup.master.data.report'

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
        self.env['master.data.report'].search([]).sudo().unlink()
        list_records = self.env['master.data.attendance'].sudo().search([('attendance_time', '>=', self.from_date),
                                                                         ('attendance_time', '<=', self.to_date)])
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
                    'attendance_time': r.attendance_time,
                    'month': r.month
                }
                self.env['master.data.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo công thô',
                'res_model': 'master.data.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")


