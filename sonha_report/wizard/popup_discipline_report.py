from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupDisciplineReport(models.TransientModel):
    _name = 'popup.discipline.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Công ty", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")

    def action_confirm(self):
        self.env['discipline.report'].search([]).sudo().unlink()
        list_records = self.env['person.discipline'].sudo().search([('date_sign', '>=', self.from_date),
                                                                    ('date_sign', '<=', self.to_date)])
        if self.company_id:
            employee_record = self.env['employee.rel'].sudo().search([('person_discipline', 'in', list_records.ids),
                                                                      ('name.company_id', '=', self.company_id.id)])
        if self.department_id and not self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.department.id == self.department_id.id)
        if self.employee_id:
            employee_record = employee_record.filtered(lambda x: x.name.id == self.employee_id.id)

        if employee_record:
            for r in employee_record:
                vals = {
                    'object_discipline': r.person_discipline.object_discipline.id,
                    'person_discipline': r.name.name,
                    'date_discipline': r.person_discipline.date_discipline,
                    'reason': r.person_discipline.reason,
                    'content': r.person_discipline.content,
                    'discipline_number': r.person_discipline.discipline_number,
                    'state': r.person_discipline.state.id,
                    'form_discipline': r.person_discipline.form_discipline.id,
                    'form_discipline_properties': r.person_discipline.form_discipline_properties,
                    'date_start': r.person_discipline.date_start,
                    'date_end': r.person_discipline.date_end,
                    'date_sign': r.person_discipline.date_sign,
                    'amount': r.person_discipline.amount,
                    'option': r.person_discipline.option,
                    'note': r.person_discipline.note,
                    'sign_person': r.person_discipline.sign_person.id,
                    'person_discipline_job': r.job.id,
                    'department_id': r.department.id,
                    'employee_code': r.emp_code,
                }
                self.env['discipline.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quyết định kỷ luật',
                'res_model': 'discipline.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")