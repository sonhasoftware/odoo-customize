from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class SonHaKPI(models.Model):
    _name = 'sonha.kpi'

    name = fields.Char(string="Tên")
    employee_id = fields.Many2one('hr.employee')
    kpi_rel = fields.One2many('sonha.kpi.rel', 'kpi_id', string="KPI")
    hide_kpi_column = fields.Many2one('config.column')
    log_kpi = fields.Boolean('Log', default=False, compute="log_kpi_date")
    month = fields.Selection([('1', 1),
                              ('2', 2),
                              ('3', 3),
                              ('4', 4),
                              ('5', 5),
                              ('6', 6),
                              ('7', 7),
                              ('8', 8),
                              ('9', 8),
                              ('10', 10),
                              ('11', 11),
                              ('12', 12),],
                             string="Tháng")
    year = fields.Integer('Năm')

    # @api.constrains('year')
    # def validate_year(self):
    #     now = datetime.datetime.now()
    #     for r in self:
    #         if r.year and r.year < now.date().year:
    #             raise ValidationError('Năm không được bé hơn năm hiện tại!')

    @api.constrains('year')
    def validate_year(self):
        raise ValidationError('Năm không')

    def log_kpi_date(self):
        for r in self:
            date_kpi = self.check_condition_date_kpi(r)
            date = self.check_condition_date(r)
            if date and date_kpi and date_kpi <= date:
                r.log_kpi = True
            else:
                r.log_kpi = False

    def check_condition_date_kpi(self, r):
        now = datetime.datetime.now()
        date_kpi = None
        if r.month:
            if r.month == '1':
                month = 1
            elif r.month == '2':
                month = 2
            elif r.month == '3':
                month = 3
            elif r.month == '4':
                month = 4
            elif r.month == '5':
                month = 5
            elif r.month == '6':
                month = 6
            elif r.month == '7':
                month = 7
            elif r.month == '8':
                month = 8
            elif r.month == '9':
                month = 9
            elif r.month == '10':
                month = 10
            elif r.month == '11':
                month = 11
            elif r.month == '12':
                month = 12
            date_kpi = now.date().replace(day=1, month=month, year=r.year)
            date_kpi = date_kpi + relativedelta(days=-1, months=1)
        return date_kpi

    def check_condition_date(self, r):
        date = None
        now = datetime.datetime.now()
        if r.employee_id.number > 1:
            date = now.date() - relativedelta(days=r.employee_id.number)
        elif r.employee_id.date and (not r.employee_id.number or r.employee_id.number < 1):
            date = r.employee_id.date
        return date
