from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, time, timedelta, date
from dateutil.relativedelta import relativedelta

class PopupSyntheticLeaveReport(models.TransientModel):
    _name = 'popup.synthetic.leave.report'

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

    @api.constrains('from_date', 'to_date')
    def _check_date(self):
        min_date = date(2025, 11, 1)
        for rec in self:
            if rec.from_date < min_date:
                raise ValidationError("Từ ngày không được trước 01/11/2025!")
            if rec.to_date < min_date:
                raise ValidationError("Đến ngày không được trước 01/11/2025!")
    def default_from_date(self):
        now = datetime.today().date()
        from_date = now.replace(day=1)
        return from_date

    def default_to_date(self):
        now = datetime.today().date()
        to_date = (now.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return to_date

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
        self.env['leave.report'].search([]).sudo().unlink()
        company_id = self.company_id.id if self.company_id else 0
        department_id = self.department_id.id if self.department_id else 0
        employee_id = self.employee_id.id if self.employee_id else 0
        from_date = self.from_date if self.from_date else date.today()
        to_date = self.to_date if self.to_date else date.today()
        query = "SELECT * FROM public.fn_bao_cao_nxt_phep_th(%s, %s, %s, %s, %s)"
        self.env.cr.execute(query, (company_id, from_date, to_date, department_id, employee_id))
        rows = self.env.cr.dictfetchall()
        if rows:
            for r in rows:
                vals = {
                    'ns_id': r["ns_id"],
                    'ma_ns': r["ma_ns"],
                    'ten_ns': r["ten_ns"],
                    'ton_dau': r["ton_dau"],
                    'nhap': r["nhap"],
                    'xuat': r["xuat"],
                    'ton_cuoi': r["ton_cuoi"]
                }
                self.env['leave.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo phép chi tiết',
                'res_model': 'leave.report',
                'views': [(self.env.ref('sonha_report.leave_report_th_tree_view').id, 'tree')],
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không tìm thấy dữ liệu!")






















