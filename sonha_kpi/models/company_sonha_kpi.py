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
    kpi_month_filtered_ids = fields.One2many(
        'sonha.kpi.month',
        compute='_compute_filtered_kpis',
        string='KPI tháng theo tháng đã chọn',
        readonly=False
    )
    url = fields.Char("URL")
    check_sent = fields.Boolean(compute="get_check_sent")

    @api.onchange('month')
    def get_check_sent(self):
        for r in self:
            if r.month == 0:
                r.check_sent = False
            else:
                if r.kpi_month_filtered_ids and not r.kpi_month_filtered_ids[0].is_sent:
                    r.check_sent = True
                else:
                    r.check_sent = False

    @api.onchange('month', 'kpi_month')
    def _compute_filtered_kpis(self):
        for rec in self:
            if rec.month != 0:
                rec.kpi_month_filtered_ids = rec.kpi_month.filtered(lambda r: r.month_filter == rec.month)
            else:
                rec.kpi_month_filtered_ids = rec.kpi_month

    def action_sent_hr(self):
        for r in self:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            r.url =(f"{base_url}/kpi/form?department_id={r.department_id.id}&month={r.month}&year={r.year}")
            template = self.env.ref('sonha_kpi.template_sent_mail_hr_kpi')
            template.send_mail(r.id, force_send=True)
            for record in r.kpi_month_filtered_ids:
                record.sudo().write({'is_sent': True})

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



    # @api.constrains('year')
    # def validate_year(self):
    #     now = datetime.datetime.now()
    #     for r in self:
    #         if r.year and r.year < now.date().year:
    #             raise ValidationError('Năm không được bé hơn năm hiện tại!')

    def unlink(self):
        for r in self:
            self.env['sonha.kpi.result.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['report.kpi.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['sonha.kpi.year'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['plan.kpi.year'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
            self.env['sonha.kpi.month'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
        return super(CompanySonHaKPI, self).unlink()


