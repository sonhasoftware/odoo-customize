from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupEmployeeShiftReport(models.TransientModel):
    _name = 'popup.employee.shift.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True,
                                 domain="[('id', 'in', allowed_company_ids)]")
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên")
    employee_domain = fields.Binary(compute="_compute_employee_domain")

    @api.onchange("company_id", "department_id")
    def _compute_employee_domain(self):
        for rec in self:
            domain = []
            if rec.department_id:
                domain = [("department_id", "=", rec.department_id.id)]
            elif rec.company_id:
                domain = [("company_id", "=", rec.company_id.id)]
            rec.employee_domain = domain

    def action_confirm(self):
        self.env['employee.shift.report'].search([]).sudo().unlink()
        list_records = self.env['employee.attendance'].sudo().search([('date', '>=', self.from_date),
                                                                      ('date', '<=', self.to_date)])
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
                    'weekday': r.weekday,
                    'date': r.date,
                    'shift': r.shift.id,
                    'employee_code': r.employee_id.employee_code,
                }
                self.env['employee.shift.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo ca làm việc',
                'res_model': 'employee.shift.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")

