from odoo import models, fields, api


class WizardBookCarReport(models.TransientModel):
    _name = 'wizard.book.car.report'

    company_id = fields.Many2one('res.company', string="Công ty")
    department_id = fields.Many2one('hr.department', string="Phòng ban")
    start_date = fields.Date("Từ ngày", required=True)
    end_date = fields.Date("Đến ngày", required=True)
    status = fields.Selection([('draft', "Nháp"),
                               ('waiting', "Chờ duyệt"),
                               ('approved', "Đã duyệt"),
                               ('exist_car', "Cấp xe"),
                               ('issuing_card', "Cấp thẻ"),
                               ('cancel', "Hủy")], string="Trạng thái")
    state = fields.Selection([('complete', "Hoàn thành"),
                              ('not_complete', "Chưa hoàn thành")], string="Tình trạng")

    def action_confirm(self):
        records = self.env['book.car'].sudo().search([('start_date', '>=', self.start_date),
                                                      ('start_date', '<=', self.end_date)])
        if self.company_id:
            records = records.filtered(lambda x: x.company_id.id == self.company_id.id)
        if self.department_id:
            records = records.filtered(lambda x: x.department_id.id == self.department_id.id)
        if self.status:
            records = records.filtered(lambda x: x.type == self.status)
            if self.state:
                if self.status == 'exist_car' and self.state == 'complete':
                    records = records.filtered(lambda x: x.status_exist_car == 'done')
                else:
                    records = records.filtered(lambda x: x.status_exist_car != 'done')
                if self.status == 'issuing_card' and self.state == 'complete':
                    records = records.filtered(lambda x: x.status_issuing_card == 'done')
                else:
                    records = records.filtered(lambda x: x.status_issuing_card != 'done')
        return {
            'type': 'ir.actions.act_window',
            'name': 'Kết quả báo cáo',
            'res_model': 'book.car',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', records.ids)],
            'target': 'current',
        }