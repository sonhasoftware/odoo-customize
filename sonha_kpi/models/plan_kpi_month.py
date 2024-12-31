from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PlanKPIMonth(models.Model):
    _name = 'plan.kpi.month'

    kpi_year = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn", domain="[('sonha_kpi', '=', sonha_kpi)]")
    month = fields.Integer("Tháng")
    kpi_month = fields.Char("Hạng mục nhỏ")
    start_date = fields.Date('Ngày bắt đầu', require=True)
    end_date = fields.Date(string="Ngày hoàn thành", require=True)

    sonha_kpi = fields.Many2one('company.sonha.kpi')

