from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupSonhaContractReport(models.TransientModel):
    _name = 'popup.sonha.contract.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    contract_type_id = fields.Many2one('hr.contract.type', string="Kiểu hợp đồng")
    status = fields.Selection([('draft', "Mới"),
                               ('open', "Đang chạy"),
                               ('close', "Đã hết hạn"),
                               ('cancel', "Đã hủy")], string="Trạng thái")

    def action_confirm(self):
        self.env['sonha.contract.report'].search([]).sudo().unlink()
        list_records = self.env['hr.contract'].sudo().search([('date_start', '>=', self.from_date),
                                                              ('date_start', '<=', self.to_date)])
        if self.company_id and not self.department_id:
            list_records = list_records.filtered(lambda x: x.employee_id.company_id.id == self.company_id.id)
        if self.department_id:
            list_records = list_records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.contract_type_id:
            list_records = list_records.filtered(lambda x: x.contract_type_id.id == self.contract_type_id.id)
        if self.status and self.status != 'open':
            list_records = list_records.filtered(lambda x: x.state == self.status)
        if self.status and self.status == 'open':
            open_contract = list_records.filtered(lambda x: x.employee_id.status_employee != 'quit_job' and x.state == 'open')
            employee_open = open_contract.mapped('employee_id.id')
            list_contract_open = open_contract.ids
            list_contract = list_records.filtered(lambda x: x.employee_id.status_employee != 'quit_job').sorted(key=lambda x: x.create_date, reverse=True)
            for rec in list_contract:
                if rec.employee_id.id not in employee_open:
                    list_contract_open.append(rec.id)
                    employee_open.append(rec.employee_id.id)
            list_records = list_records.filtered(lambda x: x.id in list_contract_open)
        if list_records:
            for r in list_records:
                vals = {
                    'name': r.name,
                    'employee_id': r.employee_id.id,
                    'employee_code': r.employee_code,
                    'date_start': r.date_start,
                    'date_end': r.date_end,
                    'structure_type_id': r.structure_type_id.id,
                    'department_id': r.department_id.id,
                    'job_id': r.job_id.id,
                    'contract_type_id': r.contract_type_id.id,
                    'resource_calendar_id': r.resource_calendar_id.id,
                    'status': r.state,
                }
                self.env['sonha.contract.report'].sudo().create(vals)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Báo cáo hợp đồng',
                'res_model': 'sonha.contract.report',
                'view_mode': 'tree',
                'target': 'current',
            }
        else:
            raise ValidationError("Không có dữ liệu!")


