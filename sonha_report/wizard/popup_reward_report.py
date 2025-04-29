from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupRewardReport(models.TransientModel):
    _name = 'popup.reward.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Công ty", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")

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