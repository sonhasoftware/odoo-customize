from odoo import api, fields, models, _

import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class ParentKPIYear(models.Model):
    _name = 'parent.kpi.year'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    year = fields.Integer('Năm', default=lambda self: datetime.date.today().year)
    month = fields.Integer('Tháng')

    status = fields.Selection([('draft', 'Nháp'),
                               ('waiting', 'Chờ duyệt'),
                               ('done', 'Đã duyệt')],
                              string='Trạng thái', default='draft')

    plan_kpi_year = fields.One2many('plan.kpi.year', 'plan_kpi_year')
    sonha_kpi = fields.Many2one('company.sonha.kpi')

    @api.constrains('department_id', 'year', 'id')
    def validate_parent_plan_kpi_month(self):
        for r in self:
            exit_kpi = self.env['parent.kpi.year'].sudo().search([('department_id', '=', r.department_id.id),
                                                                  ('year', '=', r.year),
                                                                  ('id', '!=', r.id)])
            if exit_kpi:
                raise ValidationError(f"Đã có một kế hoạch cho phòng {r.department_id.name} trong năm {r.year} rồi!")

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
                elif exit_kpi:
                    kpi = exit_kpi
                r.sonha_kpi = kpi.id
                for kpi_rc in r.plan_kpi_year:
                    self.env['sonha.kpi.year'].sudo().create({
                        'name': kpi_rc.name,
                        'start_date': kpi_rc.start_date,
                        'end_date': kpi_rc.end_date,
                        'kpi_year': kpi_rc.kpi_year,
                        'ti_le_monh_one': kpi_rc.ti_le_monh_one,
                        'ti_le_monh_two': kpi_rc.ti_le_monh_two,
                        'ti_le_monh_three': kpi_rc.ti_le_monh_three,
                        'ti_le_monh_four': kpi_rc.ti_le_monh_four,
                        'ti_le_monh_five': kpi_rc.ti_le_monh_five,
                        'ti_le_monh_six': kpi_rc.ti_le_monh_six,
                        'ti_le_monh_seven': kpi_rc.ti_le_monh_seven,
                        'ti_le_monh_eight': kpi_rc.ti_le_monh_eight,
                        'ti_le_monh_nigh': kpi_rc.ti_le_monh_nigh,
                        'ti_le_monh_ten': kpi_rc.ti_le_monh_ten,
                        'ti_le_monh_eleven': kpi_rc.ti_le_monh_eleven,
                        'ti_le_monh_twenty': kpi_rc.ti_le_monh_twenty,
                        'sonha_kpi': kpi.id,
                        'parent_kpi_year': r.id,
                    })
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI năm")
            r.status = 'done'

    def action_sent(self):
        for r in self:
            if r.plan_kpi_year:
                if r.create_uid.id == self.env.user.id and r.status == 'draft':
                    r.status = 'waiting'
                else:
                    raise ValidationError("Bạn không có quyền gửi duyệt đến cấp lãnh đạo")
            else:
                raise ValidationError("Chưa có dữ liệu kế hoạch KPI năm")

    def action_back(self):
        for r in self:
            records = self.env['plan.kpi.month'].sudo().search([('department_id', '=', r.department_id.id),
                                                                  ('year', '=', r.year)])
            if records:
                raise ValidationError("Không được phép hoàn duyệt khi có KPI tháng!")
            else:
                r.status = 'draft'
                self.env['sonha.kpi.year'].sudo().search([('parent_kpi_year', '=', r.id)]).sudo().unlink()

    def unlink(self):
        for r in self:
            if r.status == 'done':
                raise ValidationError("Không được phép xóa khi đã duyệt")
            else:
                self.env['plan.kpi.year'].search([('plan_kpi_year', '=', r.id)]).sudo().unlink()
        return super(ParentKPIYear, self).unlink()

