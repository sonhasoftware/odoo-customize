from odoo import models, fields
import datetime
from dateutil.relativedelta import relativedelta


class PopupWizardReportKpiMonthRel(models.TransientModel):
    _name = 'popup.wizard.report.kpi.month.rel'

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
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
                              ('twelve', 12), ], string="Tháng", required=True,
                             default=lambda self: self._get_default_month())
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


    def _get_default_month(self):
        now = datetime.date.today()
        pre_month_time = now + relativedelta(months=-1)
        pre_month = pre_month_time.month
        if pre_month == 1:
            return 'one'
        elif pre_month == 2:
            return 'two'
        elif pre_month == 3:
            return 'three'
        elif pre_month == 4:
            return 'four'
        elif pre_month == 5:
            return 'five'
        elif pre_month == 6:
            return 'six'
        elif pre_month == 7:
            return 'seven'
        elif pre_month == 8:
            return 'eight'
        elif pre_month == 9:
            return 'nine'
        elif pre_month == 10:
            return 'ten'
        elif pre_month == 11:
            return 'eleven'
        elif pre_month == 12:
            return 'twelve'
        else:
            return None