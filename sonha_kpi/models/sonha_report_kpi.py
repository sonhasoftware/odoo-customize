from odoo import models, fields, api


class ReportKPI(models.Model):
    _name = 'report.kpi'
    _description = 'KPI Report'

    department_id = fields.Many2one('hr.department', string="Phòng ban")
    year = fields.Integer('Năm')
    start_date = fields.Date('Ngày')
    stt = fields.Char(string='STT')
    month = fields.Char(string='Tháng')
    workload = fields.Float(string='Khối lượng công việc thực hiện')
    quality = fields.Char(string='Chất lượng công việc thực hiện')
    discipline = fields.Char(string='Chấp hành nội quy, quy chế, kỷ luật lao động')
    improvement = fields.Char(string='Cải tiến, đề xuất, sáng kiến')
    total_points_before = fields.Char(string='Σ Điểm đạt (trước khi + điểm tiến bộ)')
    symbol_before = fields.Char(string='Ký hiệu (trước khi + điểm tiến bộ)')
    progress_points = fields.Char(string='Điểm Tiến bộ (+/-)')
    total_points_after = fields.Float(string='Σ Điểm đạt (Đơn vị ĐG)')
    symbol_after = fields.Char(string='Ký hiệu (sau khi + điểm tiến bộ)')
    classification = fields.Char(string='Xếp loại')
    plan = fields.Char(string='Kế hoạch')
    criteria_achievement = fields.Char(string='TH theo các tiêu chí')

    tq_workload = fields.Float(string='Khối lượng công việc thực hiện thẩm quyền')
    tq_quality = fields.Char(string='Chất lượng công việc thực hiện')
    tq_discipline = fields.Char(string='Chấp hành nội quy, quy chế, kỷ luật lao động')
    tq_improvement = fields.Char(string='Cải tiến, đề xuất, sáng kiến')
    tq_total_points_before = fields.Char(string='Σ Điểm đạt (trước khi + điểm tiến bộ)')
    tq_symbol_before = fields.Char(string='Ký hiệu (trước khi + điểm tiến bộ)')
    tq_progress_points = fields.Char(string='Điểm Tiến bộ (+/-)')
    tq_total_points_after = fields.Float(string='Σ Điểm đạt (Đơn vị ĐG)')
    tq_symbol_after = fields.Char(string='Ký hiệu (sau khi + điểm tiến bộ)')
    tq_classification = fields.Char(string='Xếp loại')
    tq_plan = fields.Char(string='Kế hoạch')
    tq_criteria_achievement = fields.Char(string='TH theo các tiêu chí')

