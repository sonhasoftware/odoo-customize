from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PlanKPIYear(models.Model):
    _name = 'plan.kpi.year'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm')
    name = fields.Char("Hạng mục lớn")
    start_date = fields.Date('Bắt đầu')
    end_date = fields.Date("Hoàn thành")
    kpi_year = fields.Float("KPI KH cả năm")

    ti_le_monh_one = fields.Float("T1")
    ti_le_monh_two = fields.Float("T2")
    ti_le_monh_three = fields.Float("T3")
    ti_le_monh_four = fields.Float("T4")
    ti_le_monh_five = fields.Float("T5")
    ti_le_monh_six = fields.Float("T6")
    ti_le_monh_seven = fields.Float("T7")
    ti_le_monh_eight = fields.Float("T8")
    ti_le_monh_nigh = fields.Float("T9")
    ti_le_monh_ten = fields.Float("T10")
    ti_le_monh_eleven = fields.Float("T11")
    ti_le_monh_twenty = fields.Float("T12")

    sonha_kpi = fields.Many2one('company.sonha.kpi')
    plan_kpi_year = fields.Many2one('parent.kpi.year')

    @api.constrains('plan_kpi_year')
    def validate_parent_plan_kpi_month(self):
        for r in self:
            if not r.plan_kpi_year.year or r.plan_kpi_year.year <= 0:
                raise ValidationError("Dữ liệu năm phải là một năm hợp lệ")

    @api.constrains('ti_le_monh_one', 'ti_le_monh_two', 'ti_le_monh_three', 'ti_le_monh_four',
                    'ti_le_monh_five', 'ti_le_monh_six', 'ti_le_monh_seven', 'ti_le_monh_eight',
                    'ti_le_monh_nigh', 'ti_le_monh_ten', 'ti_le_monh_eleven', 'ti_le_monh_twenty')
    def _check_month_values(self):
        for r in self:
            sum_month = r.ti_le_monh_one + r.ti_le_monh_two + r.ti_le_monh_three + r.ti_le_monh_four + r.ti_le_monh_five + r.ti_le_monh_six + r.ti_le_monh_seven + r.ti_le_monh_eight + r.ti_le_monh_nigh + r.ti_le_monh_ten + r.ti_le_monh_eleven + r.ti_le_monh_twenty
            if sum_month > r.kpi_year + 0.000001 or not r.kpi_year:
                raise ValidationError(f"Tổng % các tháng của hạng mục {r.name} lớn hơn KPI dự kiến cả năm")
            else:
                pass
            if r.start_date and r.end_date:
                months_to_check = [r.ti_le_monh_one, r.ti_le_monh_two,
                                   r.ti_le_monh_three, r.ti_le_monh_four,
                                   r.ti_le_monh_five, r.ti_le_monh_six,
                                   r.ti_le_monh_seven, r.ti_le_monh_eight,
                                   r.ti_le_monh_nigh, r.ti_le_monh_ten,
                                   r.ti_le_monh_eleven, r.ti_le_monh_twenty]

                start_month = r.start_date.month
                end_month = r.end_date.month
                for month in range(1, 13):
                    if month < start_month or month > end_month:
                        if months_to_check[month - 1] != 0.0:
                            raise ValidationError(f"Tháng {month} nằm ngoài phạm vi ngày bắt đầu và ngày kết thúc.")
            else:
                raise ValidationError("Phải điền dữ liệu ngày bắt đầu và ngày kết thúc trước")

    @api.constrains('kpi_year')
    def validate_kpi_kh_year(self):
        for r in self:
            kh_kpi = self.env['sonha.kpi.year'].search([('year', '=', r.year),
                                                        ('sonha_kpi', '=', r.sonha_kpi.id)])
            if sum(kh_kpi.mapped('kpi_year')) > 1:
                raise ValidationError("KPI kế hoạch cả năm không được vượt quá 100%")
            
    def filter_department_year(self, record):
        if record.plan_kpi_year:
            record.year = record.plan_kpi_year.year if record.plan_kpi_year.year else ''
            record.department_id = record.plan_kpi_year.department_id.id if record.plan_kpi_year.department_id else ''

    def create(self, vals):
        record = super(PlanKPIYear, self).create(vals)
        for r in record:
            self.filter_department_year(r)
        return record
