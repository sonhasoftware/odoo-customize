from odoo import models, fields
import datetime


class PopupWizardReportKpiMonthRel(models.TransientModel):
    _name = 'popup.wizard.report.kpi.month.rel'

    department_id = fields.Many2one('hr.department', required=True)
    month = fields.Selection([('one', 1),
                              ('two', 2),
                              ('three', 3),
                              ('four', 4),
                              ('five', 5),
                              ('six', 6),
                              ('seven', 7),
                              ('eight', 8),
                              ('nine', 9),
                              ('ten', 10),
                              ('eleven', 11),
                              ('twelve', 12), ], string="Tháng", required=True)
    year = fields.Integer('Năm', required=True, default=lambda self: datetime.date.today().year)

    def action_confirm(self):
        month = self.get_month()
        base_url = '/kpi/form'
        params = {
            'department_id': self.department_id.id,
            'month': month,
            'year': self.year,
        }
        query_string = '&'.join([f"{key}={value}" for key, value in params.items() if value])

        return {
            'type': 'ir.actions.act_url',
            'url': f"{base_url}?{query_string}",
            'target': 'self',
        }

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
        elif self.month == 'nine':
            return 9
        elif self.month == 'ten':
            return 10
        elif self.month == 'eleven':
            return 11
        elif self.month == 'twelve':
            return 12
        else:
            return None