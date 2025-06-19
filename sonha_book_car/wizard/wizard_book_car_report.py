from odoo import models, fields, api


class WizardBookCarReport(models.TransientModel):
    _name = 'wizard.book.car.report'

    company_id = fields.Many2one('res.company', string="Công ty")
    department_id = fields.Many2one('hr.department', string="Phòng ban", domain="[('company_id', '=', company_id)]")
    start_date = fields.Date("Từ ngày", required=True)
    end_date = fields.Date("Đến ngày", required=True)
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('approved', "Đã duyệt"),
                               ('exist_car', "Cấp xe"),
                               ('rent_car', "Thuê xe"),
                               ('issuing_card', "Cấp thẻ"),
                               ('complete', "Hoàn thành"),
                               ('not_complete', "Chưa hoàn thành"),
                               ('cancel', "Hủy")], string="Trạng thái")
    type = fields.Selection([('exist_car', "Cấp xe"),
                             ('rent_car', "Thuê xe"),
                             ('issuing_card', "Cấp thẻ")], string="Loại")

    def action_confirm(self):
        records = self.env['book.car'].sudo().search([('start_date', '>=', self.start_date),
                                                      ('start_date', '<=', self.end_date)])
        if self.company_id and not self.department_id:
            records = records.filtered(lambda x: x.company_id.id == self.company_id.id)
        if self.department_id:
            records = records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.status:
            if self.status == 'complete':
                records = records.filtered(lambda x: x.status_exist_car == 'done' or x.status_issuing_card == 'done')
            elif self.status == 'not_complete':
                records = records.filtered(lambda x: ((x.status_exist_car != 'done' and x.status_issuing_card == 'approved') or (x.status_issuing_card != 'done' and x.status_exist_car == 'approved')) and x.status != 'cancel')
            elif self.status == 'rent_car':
                records = records.filtered(lambda x: x.type == 'exist_car' and x.is_rent)
            elif self.status == 'exist_car':
                records = records.filtered(lambda x: x.type == 'exist_car' and not x.is_rent)
            else:
                records = records.filtered(lambda x: x.type == self.status)
        if self.type:
            if self.type == 'exist_car':
                records = records.filtered(lambda x: x.type == 'exist_car' and not x.is_rent)
            if self.type == 'rent_car':
                records = records.filtered(lambda x: x.type == 'exist_car' and x.is_rent)
            if self.type == 'issuing_card':
                records = records.filtered(lambda x: x.type == 'issuing_card')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả báo cáo',
            'res_model': 'book.car',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', records.ids)],
            'target': 'current',
        }

