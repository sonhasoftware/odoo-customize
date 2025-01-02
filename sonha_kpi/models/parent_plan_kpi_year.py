from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class ParentKPIYear(models.Model):
    _name = 'parent.kpi.year'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year)
    month = fields.Integer('Tháng')

    status = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('done', 'Đã duyệt')],
                              string='Trạng thái', default='draft')

    plan_kpi_year = fields.One2many('plan.kpi.year', 'plan_kpi_year')
    sonha_kpi = fields.Many2one('company.sonha.kpi')

    def action_approval(self):
        for r in self:
            if r.plan_kpi_year:
                exit_kpi = self.env['company.sonha.kpi'].sudo().search([('department_id', '=', r.department_id.id),
                                                                   ('year', '=', r.year)])
                if not exit_kpi:
                    kpi = self.env['company.sonha.kpi'].sudo().create({
                        'department_id': r.department_id.id,
                        'year': r.year
                    })
                self.env['sonha.kpi.year'].search([('sonha_kpi', '=', r.id)]).sudo().unlink()
                for kpi in r.plan_kpi_year:
                    self.env['sonha.kpi.year'].sudo().create({
                        'name': kpi.name,
                        'start_date': kpi.start_date,
                        'end_date': kpi.end_date,
                        'kpi_year': kpi.kpi_year,
                        'ti_le_monh_one': kpi.ti_le_monh_one,
                        'ti_le_monh_two': kpi.ti_le_monh_two,
                        'ti_le_monh_three': kpi.ti_le_monh_three,
                        'ti_le_monh_four': kpi.ti_le_monh_four,
                        'ti_le_monh_five': kpi.ti_le_monh_five,
                        'ti_le_monh_six': kpi.ti_le_monh_six,
                        'ti_le_monh_seven': kpi.ti_le_monh_seven,
                        'ti_le_monh_eight': kpi.ti_le_monh_eight,
                        'ti_le_monh_nigh': kpi.ti_le_monh_nigh,
                        'ti_le_monh_ten': kpi.ti_le_monh_ten,
                        'ti_le_monh_eleven': kpi.ti_le_monh_eleven,
                        'ti_le_monh_twenty': kpi.ti_le_monh_twenty,
                        'sonha_kpi': kpi.id,
                    })
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI năm")
            r.status = 'done'

    def action_sent(self):
        for r in self:
            if r.create_uid.id == self.env.user.id and r.status == 'draft':
                r.status = 'waiting'
            else:
                raise ValidationError("Bạn không có quyền gửi duyệt đến cấp lãnh đạo")

    def action_back(self):
        for r in self:
            r.status = 'draft'