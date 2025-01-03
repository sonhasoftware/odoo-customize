from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class PlanKPIMonth(models.Model):
    _name = 'plan.kpi.month'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm')
    kpi_year = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn", domain="[('sonha_kpi', '=', sonha_kpi)]")
    month = fields.Integer("Tháng")
    kpi_month = fields.Char("Hạng mục nhỏ")
    start_date = fields.Date('Ngày bắt đầu', require=True)
    end_date = fields.Date(string="Ngày hoàn thành", require=True)

    sonha_kpi = fields.Many2one('company.sonha.kpi', compute="get_sonha_kpi")
    plan_kpi_month = fields.Many2one('parent.kpi.month')

    def validate_start_end_date(self, record):
            if record.start_date and record.end_date and record.kpi_year.start_date <= record.start_date <= record.kpi_year.end_date and record.kpi_year.start_date <= record.end_date <= record.kpi_year.end_date:
                pass
            else:
                raise ValidationError("Dữ liệu tháng phải thuộc trong khoảng dữ liệu của năm")

    @api.depends('plan_kpi_month')
    def get_sonha_kpi(self):
        for r in self:
            if r.plan_kpi_month:
                r.sonha_kpi = r.plan_kpi_month.sonha_kpi.id if r.plan_kpi_month.sonha_kpi.id else None
            else:
                r.sonha_kpi = None

    def filter_department_year(self, record):
        if record.plan_kpi_month:
            record.year = record.plan_kpi_month.year if record.plan_kpi_month.year else ''
            record.department_id = record.plan_kpi_month.department_id.id if record.plan_kpi_month.department_id else ''
            record.start_date = f'{record.plan_kpi_month.year}-{record.plan_kpi_month.month}-1' if record.plan_kpi_month.month and record.plan_kpi_month.year else ''
            record.end_date = record.start_date + relativedelta(months=1, days=-1)

    def create(self, vals):
        record = super(PlanKPIMonth, self).create(vals)
        for r in record:
            self.filter_department_year(r)
            self.validate_start_end_date(r)
        return record