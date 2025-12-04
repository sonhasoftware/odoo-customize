from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class PopupWordSlipReport(models.TransientModel):
    _name = 'popup.word.slip.report'

    from_date = fields.Date("Từ ngày", default=lambda self: self.default_from_date(), required=True)
    to_date = fields.Date("Đến ngày", default=lambda self: self.default_to_date(), required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị",
                                 default=lambda self: self.env.user.company_id, required=True,
                                 domain="[('id', 'in', allowed_company_ids)]")
    department_id = fields.Many2one('hr.department', string="Phòng ban",
                                    default=lambda self: self.default_department())
    department_domain = fields.Binary(compute="_compute_department_domain")
    employee_id = fields.Many2many('hr.employee', string="Nhân viên", default=lambda self: self.default_employee_id())
    employee_domain = fields.Binary(compute="_compute_employee_domain")

    slip_type = fields.Many2one('config.word.slip', string="Loại đơn")
    status = fields.Selection([('sent', "Nháp"),
                               ('draft', "Chờ duyệt"),
                               ('done', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái")

    def default_employee_id(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        if emp and not (self.env.user.has_group('sonha_employee.group_hr_employee') or self.env.user.has_group(
                'sonha_employee.group_back_up_employee')):
            list_emp = [emp.id]
            return list_emp
        else:
            return None

    def default_department(self):
        emp = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.user.id)], limit=1)
        department_id = emp.department_id
        if department_id:
            return department_id
        else:
            return None

    def default_from_date(self):
        now = datetime.today().date()
        from_date = now.replace(day=1)
        return from_date

    def default_to_date(self):
        now = datetime.today().date()
        to_date = (now.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return to_date

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
        self.env['word.slip.report'].search([]).sudo().unlink()
        list_records = self.env['word.slip'].sudo().search([('from_date', '>=', self.from_date),
                                                           ('from_date', '<=', self.to_date)]).word_slip

        if self.company_id and not self.department_id and not self.employee_id:
            list_records = list_records.filtered(lambda x: x.company_id.id == self.company_id.id)
        if self.department_id and not self.employee_id:
            list_records = list_records.filtered(lambda x: x.department.id == self.department_id.id)
        if self.employee_id:
            list_records = list_records.filtered(lambda x: x.employee_id.id in self.employee_id.ids or bool(set(x.employee_ids.ids) & set(self.employee_id.ids)))
        if self.slip_type:
            list_records = list_records.filtered(lambda x: x.type.id == self.slip_type.id)
        if self.status:
            list_records = list_records.filtered(lambda x: x.status == self.status)
        if list_records:
            for r in list_records:
                from_date = []
                to_date = []
                for child in r.word_slip_id:
                    if child.from_date:
                        if child.time_to and child.type.date_and_time == 'time':
                            from_date.append(f"{child.from_date.strftime('%d/%m/%Y')} {round(child.time_to, 2)}h")
                        if child.start_time == 'first_half' and child.type.date_and_time == 'date':
                            from_date.append(f"{child.from_date.strftime('%d/%m/%Y')} (Nửa ca đầu)")
                        if child.start_time == 'second_half' and child.type.date_and_time == 'date':
                            from_date.append(f"{child.from_date.strftime('%d/%m/%Y')} (Nửa ca sau)")
                    if child.to_date:
                        if child.time_from and child.type.date_and_time == 'time':
                            to_date.append(f"{child.to_date.strftime('%d/%m/%Y')} {round(child.time_from, 2)}h")
                        if child.end_time == 'first_half' and child.type.date_and_time == 'date':
                            to_date.append(f"{child.to_date.strftime('%d/%m/%Y')} (Nửa ca đầu)")
                        if child.end_time == 'second_half' and child.type.date_and_time == 'date':
                            to_date.append(f"{child.to_date.strftime('%d/%m/%Y')} (Nửa ca sau)")
                list_emp = r.employee_ids.ids or ([r.employee_id.id] if r.employee_id else [])
                vals = {
                    'employee_ids': [(6, 0, list_emp)],
                    'department_id': r.department.id,
                    'slip_code': r.code,
                    'slip_type': r.type.id,
                    'from_date': ",\n".join(from_date) if from_date else "Không có dữ liệu",
                    'to_date': ",\n".join(to_date) if to_date else "Không có dữ liệu",
                    'status': r.status,
                    'duration': r.duration,
                    'create_employee': r.create_uid.id,
                    'slip_create_date': r.create_date,
                    }
                self.env['word.slip.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo đơn từ',
                'res_model': 'word.slip.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")


