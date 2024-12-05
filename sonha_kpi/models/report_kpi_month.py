from odoo import api, fields, models, _


class ReportKpiMonth(models.Model):
    _name = 'report.kpi.month'

    department_id = fields.Many2one('hr.department')
    year = fields.Integer('Năm')
    small_items_each_month = fields.Many2one('sonha.kpi.month', string="Nội dung CV KPI của tháng")
    kpi_year_id = fields.Many2one('sonha.kpi.year', string="Hạng mục lớn",
                                  domain="[('sonha_kpi', '=', sonha_kpi)]")
    start_date = fields.Date('Ngày bắt đầu')
    end_date = fields.Date("Ngày hoàn thành")

    dv_amount_work = fields.Float("khối lượng CVTH", default=0)
    dv_matter_work = fields.Float("Chất lượng CVTH", default=0)
    dv_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    dv_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    dv_description = fields.Text("Mô tả chi tiết công việc")

    tq_amount_work = fields.Float("khối lượng CVTH", default=0)
    tq_matter_work = fields.Float("Chất lượng CVTH", default=0)
    tq_comply_regulations = fields.Float("Chấp hành nội quy, quy chế", default=0)
    tq_initiative = fields.Float("Cải tiến, đề xuất, sáng kiến", default=0)
    tq_description = fields.Text("Nhận xét chung của cấp có thẩm quyền")
    sonha_kpi = fields.Many2one('company.sonha.kpi')

