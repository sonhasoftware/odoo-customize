from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class CompanySonHaKPI(models.Model):
    _name = 'company.sonha.kpi'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year)

    kpi_year = fields.One2many('sonha.kpi.year', 'sonha_kpi')
    kpi_month = fields.One2many('sonha.kpi.month', 'sonha_kpi')
    kpi_result_month = fields.One2many('sonha.kpi.result.month', 'sonha_kpi')

    @api.constrains('year')
    def validate_year(self):
        now = datetime.datetime.now()
        for r in self:
            if r.year and r.year < now.date().year:
                raise ValidationError('Năm không được bé hơn năm hiện tại!')

    def unlink(self):
        for r in self:
            self.env['sonha.kpi.result.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['report.kpi.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['sonha.kpi.year'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
        return super(CompanySonHaKPI, self).unlink()
