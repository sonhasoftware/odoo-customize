from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class ParentKPIMonth(models.Model):
    _name = 'parent.kpi.month'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year)
    month = fields.Integer('Tháng')
    status = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('done', 'Đã duyệt')],
                              string='Trạng thái', default='draft')

    plan_kpi_month = fields.One2many('plan.kpi.month', 'plan_kpi_month')
    sonha_kpi = fields.Many2one('company.sonha.kpi', compute="filter_sonha_kpi")

    @api.constrains('year')
    def validate_year(self):
        now = datetime.datetime.now()
        for r in self:
            if r.year and r.year < now.date().year:
                raise ValidationError('Năm không được bé hơn năm hiện tại!')


    @api.constrains('month', 'department_id', 'year', 'id')
    def validate_parent_plan_kpi_month(self):
        for r in self:
            exit_kpi = self.env['parent.kpi.month'].sudo().search([('department_id', '=', r.department_id.id),
                                                                  ('year', '=', r.year),
                                                                  ('month', '=', r.month),
                                                                  ('id', '!=', r.id)])
            if exit_kpi:
                raise ValidationError(f"Đã có một kế hoạch cho phòng {r.department_id.name} trong tháng {r.month} rồi!")

    @api.constrains('month')
    def validate_month(self):
        for r in self:
            if 1 > r.month or r.month > 12:
                raise ValidationError("Dữ liệu tháng phải là một tháng hợp lệ trong năm!")

    @api.depends('department_id', 'year')
    def filter_sonha_kpi(self):
        for r in self:
            kpi = self.env['company.sonha.kpi'].sudo().search([('department_id', '=', r.department_id.id),
                                                               ('year', '=', r.year)])
            r.sonha_kpi = kpi.id

    def action_month_sent(self):
        for r in self:
            if r.plan_kpi_month:
                if r.department_id.id == self.env.user.employee_id.department_id.id and r.status == 'draft':
                    r.status = 'waiting'
                else:
                    raise ValidationError("Bạn không có quyền gửi duyệt đến cấp lãnh đạo")
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI tháng")

    def action_to_draft(self):
        for r in self:
            r.status = 'draft'

    def action_month_approval(self):
        for r in self:
            if r.plan_kpi_month:
                kpi = self.env['company.sonha.kpi'].sudo().search([('department_id', '=', r.department_id.id),
                                                                   ('year', '=', r.year)])
                if kpi:
                    for kpi_rc in r.plan_kpi_month:
                        self.env['sonha.kpi.month'].sudo().create({
                            'small_items_each_month': kpi_rc.kpi_month,
                            'start_date': kpi_rc.start_date,
                            'end_date': kpi_rc.end_date,
                            'kpi_year_id': kpi_rc.kpi_year.id,
                            'sonha_kpi': kpi.id,
                            'parent_kpi_month': r.id,
                        })
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI tháng")
            r.status = 'done'

    def action_month_back(self):
        for r in self:
            r.status = 'draft'
            self.env['sonha.kpi.month'].search([('parent_kpi_month', '=', r.id)]).sudo().unlink()
            self.env['sonha.kpi.month'].calculating_dvdgkpi_tqdgkpi(r)

    def write(self, vals):
        res = super(ParentKPIMonth, self).write(vals)
        for r in self:
            self.write_month_plan_kpi(r)
        return res

    def write_month_plan_kpi(self, record):
        plan_kpi_month = self.env['plan.kpi.month'].sudo().search([('plan_kpi_month', '=', record.id)])
        if plan_kpi_month:
            for r in plan_kpi_month:
                r.validate_year(r)
                r.filter_department_year(r)
                r.validate_create_write(r)

    def unlink(self):
        for r in self:
            if r.status != 'draft':
                raise ValidationError("Chỉ được xóa khi trạng thái là nháp!")
            else:
                self.env['plan.kpi.month'].search([('plan_kpi_month', '=', r.id)]).sudo().unlink()
        return super(ParentKPIMonth, self).unlink()

    def get_status_label(self):
        return dict(self._fields['status'].selection).get(self.status)