from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta, date
from dateutil.relativedelta import relativedelta

class PopupEmployeeAttendanceReport(models.TransientModel):
    _name = 'popup.employee.attendance.report'

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


    def action_confirm(self):
        self.env['employee.attendance.report'].search([]).sudo().unlink()
        company_id = self.company_id.id if self.company_id else 0
        department_id = self.department_id.id if self.department_id else 0
        employee_id = self.employee_id.id if self.employee_id else 0
        from_date = self.from_date if self.from_date else date.today()
        to_date = self.to_date if self.to_date else date.today()
        query = """select cct.employee_id as ns_id,
                        cct.department_id as bo_phan_id, 
                        cct.weekday as thu,
                        cct.date as ngay,
                        cct.check_in,
                        cct.check_out,
                        cct.shift as ca,
                        cct.note as ghi_chu,
                        cct.minutes_late as phut_muon,
                        cct.minutes_early as phut_som,
                        cct.work_day as ngay_cong,
                        cct.over_time as lam_them,
                        cct.leave as nghi_phep,
                        cct.compensatory as nghi_bu,
                        cct.over_time_nb as lam_them_nb
                    from employee_attendance_v2 cct
                    left join hr_employee ns on cct.employee_id = ns.id
                    where cct.date between %(from_date)s and %(to_date)s and ns.company_id = %(company_id)s
                        AND case when %(department_id)s = 0 then 1=1 else cct.department_id = %(department_id)s end
                        AND case when %(employee_id)s = 0 then 1=1 else cct.employee_id = %(employee_id)s end;"""
        self.env.cr.execute(query, {'from_date': from_date,
                                    'to_date': to_date,
                                    'company_id': company_id,
                                    'department_id': department_id,
                                    'employee_id': employee_id})
        row = self.env.cr.dictfetchall()
        if row:
            for r in row:
                vals = {
                    'employee_id': r["ns_id"],
                    'department_id': r["bo_phan_id"],
                    'weekday': r["thu"],
                    'date': r["ngay"],
                    'check_in': r["check_in"],
                    'check_out': r["check_out"],
                    'shift': r["ca"],
                    'note': r["ghi_chu"],
                    'minutes_late': r["phut_muon"],
                    'minutes_early': r["phut_som"],
                    'work_day': r["ngay_cong"],
                    'over_time': r["lam_them"],
                    'leave': r["nghi_phep"],
                    'compensatory': r["nghi_bu"],
                    'over_time_nb': r["lam_them_nb"],
                }
                self.env['employee.attendance.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo công chi tiết',
                'res_model': 'employee.attendance.report',
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

