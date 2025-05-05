from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupSonhaEmployeeReport(models.TransientModel):
    _name = 'popup.sonha.employee.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    status_employee = fields.Selection([('working', "Đang làm việc"),
                                        ('quit_job', "Nghỉ việc")], string="Trạng thái làm việc")

    def action_confirm(self):
        self.env['sonha.employee.report'].sudo().search([]).unlink()
        if self.status_employee and self.status_employee == 'quit_job':
            list_records = self.env['hr.employee'].sudo().with_context(active_test=False).search([('date_quit', '>=', self.from_date),
                                                                                                  ('date_quit', '<=', self.to_date),
                                                                                                  ('active', '=', False)])
        elif self.status_employee and self.status_employee == 'working':
            list_records = self.env['hr.employee'].with_context(active_test=False).sudo().search([
                '|',
                ('date_quit', '>=', self.to_date),
                '&',
                ('onboard', '<=', self.to_date),
                ('onboard', '>=', self.from_date),
            ])
        else:
            list_records = self.env['hr.employee'].sudo().with_context(active_test=False).search([('onboard', '>=', self.from_date),
                                                                                                  ('onboard', '<=', self.to_date)])
        if self.company_id and not self.department_id:
            list_records = list_records.filtered(lambda x: x.company_id.id == self.company_id.id)
        if self.department_id:
            list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if list_records:
            for r in list_records:
                vals = {
                    'name': r.name,
                    'employee_code': r.employee_code,
                    'sonha_number_phone': r.sonha_number_phone,
                    'work_email': r.work_email,
                    'company_id': r.company_id.id,
                    'department_id': r.department_id.id,
                    'job_id': r.job_id.id,
                    'parent_id': r.parent_id.id,
                    'status_employee': r.status_employee,
                    'date_birthday': r.date_birthday,
                    'place_birthday': r.place_birthday,
                    'gender': r.gender,
                    'marital_status': r.marital_status,
                    'nation': r.nation,
                    'religion': r.religion,
                    'tax_code': r.tax_code,
                    'hometown': r.hometown,
                    'permanent': r.permanent_address,
                    'onboard': r.onboard,
                    'reception_date': r.reception_date,
                    'number_cccd': r.number_cccd,
                    'date_cccd': r.date_cccd,
                    'place_of_issue': r.place_of_issue,
                    'culture_level': r.culture_level,
                    # 'total_compensatory': r.total_compensatory,
                    'old_leave_blance': r.old_leave_balance,
                    'new_leave_balance': r.new_leave_balance,
                    'device_id_num': r.device_id_num,
                    'employee_type': r.employee_type,
                    'shift': r.shift.id,
                    'date_quit': r.date_quit,
                    'reason_quit': r.reason_quit,
                    'seniority_display': r.seniority_display,
                    'contract_id': r.contract_id.id,
                    'address_id': r.address_id.name,
                }
                self.env['sonha.employee.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo hồ sơ nhân sự',
                'res_model': 'sonha.employee.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")


