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
    done = fields.Integer("Số lượng hoàn Thành", compute="_get_data_number_state")
    waiting = fields.Integer("Số lượng chưa hoàn thành", compute="_get_data_number_state")
    cancel = fields.Integer("Số lượng hủy", compute="_get_data_number_state")

    @api.depends('kpi_month')
    def _get_data_number_state(self):
        for r in self:
            waiting_count = 0
            done_count = 0
            cancel_count = 0
            for data in r.kpi_month:
                if data.state == 'done':
                    done_count += 1
                elif data.state == 'waiting':
                    waiting_count += 1
                elif data.state == 'cancel':
                    cancel_count += 1
            r.waiting = waiting_count
            r.done = done_count
            r.cancel = cancel_count



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
            self.env['sonha.kpi.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
        return super(CompanySonHaKPI, self).unlink()


