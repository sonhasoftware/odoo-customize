from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class CompanySonHaKPI(models.Model):
    _name = 'company.sonha.kpi'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year)
    month = fields.Integer('Tháng')

    kpi_year = fields.One2many('sonha.kpi.year', 'sonha_kpi')
    kpi_month = fields.One2many('sonha.kpi.month', 'sonha_kpi')
    kpi_result_month = fields.One2many('sonha.kpi.result.month', 'sonha_kpi')
    plan_kpi_year = fields.One2many('plan.kpi.year', 'sonha_kpi')
    plan_kpi_month = fields.One2many('plan.kpi.month', 'sonha_kpi')

    status = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('done', 'Đã duyệt')],
                              string='Trạng thái', default='draft')

    status_month = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('done', 'Đã duyệt')],
                              string='Trạng thái', default='draft')

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
            self.env['plan.kpi.year'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
        return super(CompanySonHaKPI, self).unlink()


    def action_month_sent(self):
        for r in self:
            if r.create_uid.id == self.env.user.id and r.status_month == 'draft':
                r.status_month = 'waiting'
            else:
                raise ValidationError("Bạn không có quyền gửi duyệt đến cấp lãnh đạo")

    def action_month_approval(self):
        for r in self:
            if r.plan_kpi_month:
                self.env['sonha.kpi.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
                for kpi in r.plan_kpi_month:
                    self.env['sonha.kpi.month'].sudo().create({
                        'small_items_each_month': kpi.kpi_month,
                        'kpi_year_id': kpi.kpi_year.id,
                        'start_date': kpi.start_date,
                        'end_date': kpi.end_date,
                    })
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI năm")
            r.status = 'done'

    def action_month_back(self):
        for r in self:
            r.status_month = 'draft'
