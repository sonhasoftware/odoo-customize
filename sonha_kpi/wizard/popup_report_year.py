from odoo import models, fields
import datetime


class PopupWizardReportYear(models.TransientModel):
    _name = 'popup.wizard.report.year'

    department_id = fields.Many2one('hr.department', required=True, domain=lambda self: [('id', 'in', self.env.user.employee_id.department_ids.ids)])
    year = fields.Integer('Năm', required=True, default=lambda self: datetime.date.today().year)

    def action_confirm(self):
        docs = self.env['sonha.kpi.year'].sudo().search([('year', '=', self.year),
                                                        ('department_id', '=', self.department_id.id)])
        return self.env.ref('sonha_kpi.template_year_action').report_action(docs)