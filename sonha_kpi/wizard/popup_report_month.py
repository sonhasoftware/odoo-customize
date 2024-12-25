from odoo import models, fields
import datetime
from odoo.exceptions import UserError, ValidationError


class PopupWizardReportMonth(models.TransientModel):
    _name = 'popup.wizard.report.month'

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    month = fields.Selection([('one', 1),
                              ('two', 2),
                              ('three', 3),
                              ('four', 4),
                              ('five', 5),
                              ('six', 6),
                              ('seven', 7),
                              ('eight', 8),
                              ('nigh', 9),
                              ('ten', 10),
                              ('eleven', 11),
                              ('twenty', 12),], string="Tháng")
    year = fields.Integer('Năm', required=True, default=lambda self: datetime.date.today().year)

    def action_confirm(self):
        month = self.get_month()
        docs = self.env['sonha.kpi.result.month'].sudo().search([('year', '=', self.year),
                                                                 ('department_id', '=', self.department_id.id)])
        if month:
            docs = docs.filtered(lambda x: x.start_date.month == month)
        if docs:
            return self.env.ref('sonha_kpi.template_month_action').report_action(docs)
        else:
            raise ValidationError("Chưa có dữ liệu đánh giá tháng " + str(month) + " của phòng/ban " + self.department_id.name)

    def get_month(self):
        if self.month == 'one':
            return 1
        elif self.month == 'two':
            return 2
        elif self.month == 'three':
            return 3
        elif self.month == 'four':
            return 4
        elif self.month == 'five':
            return 5
        elif self.month == 'six':
            return 6
        elif self.month == 'seven':
            return 7
        elif self.month == 'eight':
            return 8
        elif self.month == 'nigh':
            return 9
        elif self.month == 'ten':
            return 10
        elif self.month == 'eleven':
            return 11
        elif self.month == 'twenty':
            return 12
        else:
            return None