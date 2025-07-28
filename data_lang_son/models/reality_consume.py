from odoo import api, fields, models
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta


class RealityConsume(models.Model):
    _name = 'reality.consume'

    branch = fields.Many2one('config.pumping', string="Chi trạm bơm")
    branch_id = fields.Many2one('config.branch', string="Tên chi nhánh", related="branch.branch_id")
    month = fields.Integer("Tháng")
    year = fields.Integer("Năm")
    number_filter = fields.Integer("Số filter", compute="get_number_filter")
    reality_consume = fields.One2many('reality.consume.rel', 'reality_id', string="Chi tiết")

    reality_consume_filtered_ids = fields.One2many(
        'reality.consume.rel',
        compute='_compute_filtered_reality',
        string='KPI tháng theo tháng đã chọn',
        readonly=False
    )

    check_invisible = fields.Boolean("Check điều kiện", compute="get_check_invisible")

    @api.onchange('month', 'year', 'reality_consume')
    def _compute_filtered_reality(self):
        for rec in self:

            if rec.month != 0 and rec.year != 0 and rec.number_filter == 0:
                rec.reality_consume_filtered_ids = rec.reality_consume.filtered(lambda r: r.date.month == rec.month and r.date.year == rec.year)
            elif rec.number_filter != 0:
                today = date.today()
                start_date = today - relativedelta(days=rec.number_filter) + relativedelta(days=1)
                rec.reality_consume_filtered_ids = rec.reality_consume.filtered(
                    lambda r: start_date <= r.date <= today)
            else:
                rec.reality_consume_filtered_ids = rec.reality_consume

    @api.depends('branch', 'branch.date')
    def get_number_filter(self):
        for r in self:
            r.number_filter = 0
            if r.branch and r.branch.date:
                r.number_filter = r.branch.date

    @api.depends('number_filter')
    def get_check_invisible(self):
        for r in self:
            r.check_invisible = False
            if r.number_filter != 0:
                r.check_invisible = True

    def create_reality_consume(self):
        list_branch = self.env['config.pumping'].sudo().search([])
        today = date.today()
        start_date = today.replace(day=1, month=1)

        for branch in list_branch:
            reality_id = self.sudo().search([('branch', '=', branch.id)], limit=1)
            if not reality_id:
                reality_id = self.sudo().create({'branch': branch.id})

            current_date = start_date
            while current_date <= today:
                exists = self.env['reality.consume.rel'].sudo().search([
                    ('date', '=', current_date),
                    ('reality_id', '=', reality_id.id)
                ], limit=1)
                if not exists:
                    self.env['reality.consume.rel'].sudo().create({
                        'date': current_date,
                        'reality_id': reality_id.id
                    })
                current_date += timedelta(days=1)


