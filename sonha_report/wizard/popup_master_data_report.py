from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class PopupMasterDataReport(models.TransientModel):
    _name = 'popup.master.data.report'

    from_date = fields.Date(string="Từ ngày", required=True)
    to_date = fields.Date(string="Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('department_id', '=', department_id), ('company_id', '=', company_id)]")


    def action_confirm(self):
        self.env['master.data.report'].search([]).sudo().unlink()
        list_records = self.env['master.data.attendance'].sudo().search([('attendance_time', '>=', self.from_date),
                                                                         ('attendance_time', '<=', self.to_date)])
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
                        'attendance_time': r.attendance_time,
                        'month': r.month
                    }
                    self.env['master.data.report'].sudo().create(vals)
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Báo cáo công thô',
                    'res_model': 'master.data.report',
                    'view_mode': 'tree',
                    'target': 'current',
                }
            else:
                raise ValidationError("Không có dữ liệu!")


