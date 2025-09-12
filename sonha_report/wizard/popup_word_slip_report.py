from odoo import fields, models, api
from odoo.exceptions import UserError, ValidationError


class PopupWordSlipReport(models.TransientModel):
    _name = 'popup.word.slip.report'

    from_date = fields.Date("Từ ngày", required=True)
    to_date = fields.Date("Đến ngày", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True,
                                 domain="[('id', 'in', allowed_company_ids)]")
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    employee_id = fields.Many2many('hr.employee', string="Nhân viên")
    employee_domain = fields.Binary(compute="_compute_employee_domain")

    slip_type = fields.Many2one('config.word.slip', string="Loại đơn")
    status = fields.Selection([('sent', "Nháp"),
                               ('draft', "Chờ duyệt"),
                               ('done', "Đã duyệt"),
                               ('cancel', "Hủy")], string="Trạng thái")

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
        self.env['word.slip.report'].search([]).sudo().unlink()
        list_records = self.env['word.slip'].sudo().search([('from_date', '>=', self.from_date),
                                                           ('to_date', '<=', self.to_date)]).word_slip

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
                list_emp = r.employee_ids.ids or [r.employee_id.id]
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


