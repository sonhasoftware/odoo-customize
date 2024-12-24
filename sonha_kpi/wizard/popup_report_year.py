from odoo import models, fields
import datetime
from odoo.exceptions import UserError, ValidationError


class PopupWizardReportYear(models.TransientModel):
    _name = 'popup.wizard.report.year'

    department_id = fields.Many2one('hr.department', required=True)
    year = fields.Integer('Năm', required=True, default=lambda self: datetime.date.today().year)

    def action_confirm(self):
        docs = self.env['sonha.kpi.year'].sudo().search([('year', '=', self.year),
                                                        ('department_id', '=', self.department_id.id)])
        if docs:
            return self.env.ref('sonha_kpi.template_year_action').report_action(docs)
        else:
            raise ValidationError("Chưa có dữ liệu đánh giá năm của phòng/ban " + self.department_id.name)