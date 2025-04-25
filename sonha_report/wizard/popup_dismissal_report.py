from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupDismissalReport(models.TransientModel):
    _name = 'popup.dismissal.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Công ty", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")
    type = fields.Selection([('dismissal', "Miễn nhiệm"), ('quit', "Nghỉ việc")], string="Loại", required=True)

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
                    'employee_code': r.emp_code,
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