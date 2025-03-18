from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupSyntheticWorkReport(models.TransientModel):
    _name = 'popup.synthetic.work.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")


    def action_confirm(self):
        self.env['synthetic.work.report'].search([]).sudo().unlink()
        list_records = self.env['synthetic.work'].sudo().search([('start_date', '=', self.from_date),
                                                                 ('end_date', '=', self.to_date)])
        if self.company_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
            if self.department_id:
                list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
                if self.employee_id:
                    list_records = list_records.filtered(lambda x: x.employee_id.id == self.employee_id.id)
            if list_records:
                for r in list_records:
                    vals = {
                        'employee_id': r.employee_id.id,
                        'department_id': r.department_id.id,
                        'employee_code': r.employee_code,
                        'date_work': r.date_work,
                        'apprenticeship': r.apprenticeship,
                        'probationary_period': r.probationary_period,
                        'ot_one_hundred': r.ot_one_hundred,
                        'ot_one_hundred_fifty': r.ot_one_hundred_fifty,
                        'ot_three_hundred': r.ot_three_hundred,
                        'paid_leave': r.paid_leave,
                        'number_minutes_late': r.number_minutes_late,
                        'number_minutes_early': r.number_minutes_early,
                        'shift_two_crew_three': r.shift_two_crew_three,
                        'shift_three_crew_four': r.shift_three_crew_four,
                        'on_leave': r.on_leave,
                        'compensatory_leave': r.compensatory_leave,
                        'filial_leave': r.filial_leave,
                        'grandparents_leave': r.grandparents_leave,
                        'vacation': r.vacation,
                        'public_leave': r.public_leave,
                        'total_work': r.total_work,
                        'month': r.month,
                        'hours_reinforcement': r.hours_reinforcement,
                    }
                    self.env['synthetic.work.report'].sudo().create(vals)
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Báo cáo công chi tiết',
                    'res_model': 'synthetic.work.report',
                    'view_mode': 'tree',
                    'target': 'current',
                }
            else:
                raise ValidationError("Không có dữ liệu!")

