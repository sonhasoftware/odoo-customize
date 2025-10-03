from odoo import models, fields
import datetime


class PopupWizardReport(models.TransientModel):
    _name = 'popup.wizard.report'

    department_id = fields.Many2one('hr.department', string="Phòng ban", required=True)
    year = fields.Integer('Năm', required=True, default=lambda self: datetime.date.today().year)

    def action_confirm(self):
        self.env['report.kpi'].sudo().search([]).unlink()
        self._prepare_report_data()
        docs = self.env['report.kpi'].sudo().search([
            ('department_id', '=', self.department_id.id),
            ('year', '=', self.year)
        ])
        return self.env.ref('sonha_kpi.performance_report_action').report_action(docs)

    def _prepare_report_data(self):
        months = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12',
                  'Cả năm', 'Qúy 1', 'Qúy 2', 'Qúy 3', 'Qúy 4']

        result_month = self.env['sonha.kpi.result.month'].sudo().search([
            ('department_id', '=', self.department_id.id),
            ('year', '=', self.year)
        ])
        month_before = None
        for month in months:
            if month not in ['Cả năm', 'Qúy 1', 'Qúy 2', 'Qúy 3', 'Qúy 4']:
                data_filter = self.filter_data(month, result_month)
                data_before = self.filter_data(month_before, result_month)
                date = data_filter[-1].start_date if data_filter else None
                total, symbol_before, total_points_after, symbol_after, classification, progress_points = self.calculate_classification_and_points(
                    data_filter, data_before)
                total_tq, symbol_before_tq, total_points_after_tq, symbol_after_tq, classification_tq, progress_points_tq = self.calculate_classification_and_points_authorization(
                    data_filter, data_before)

                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'start_date': str(date) if data_filter else None,
                    'month': month + '/' + str(self.year),
                    'workload': round(sum(data_filter.mapped('quy_doi_dv_amount_work')), 2) if data_filter else 0,
                    'quality': str(round(sum(data_filter.mapped('quy_doi_dv_matter_work')), 2)) if data_filter else '',
                    'discipline': str(round(sum(data_filter.mapped('quy_doi_dv_comply_regulations')), 2)) if data_filter else '',
                    'improvement': str(round(sum(data_filter.mapped('quy_doi_dv_initiative')), 2)) if data_filter else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_before) if symbol_before else '',
                    'progress_points': str(progress_points) if progress_points else '',
                    'total_points_after': (round(total_points_after, 2)) if total_points_after else '',
                    'symbol_after': str(symbol_after) if symbol_after else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': round(sum(data_filter.mapped('quy_doi_tq_amount_work')), 2) if data_filter else 0,
                    'tq_quality': str(round(sum(data_filter.mapped('quy_doi_tq_matter_work')), 2)) if data_filter else '',
                    'tq_discipline': str(round(sum(data_filter.mapped('quy_doi_tq_comply_regulations')), 2)) if data_filter else '',
                    'tq_improvement': str(round(sum(data_filter.mapped('quy_doi_tq_initiative')), 2)) if data_filter else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_before_tq) if symbol_before_tq else '',
                    'tq_progress_points': str(progress_points_tq) if progress_points_tq else '',
                    'tq_total_points_after': (round(total_points_after_tq, 2)) if total_points_after_tq else '',
                    'tq_symbol_after': str(symbol_after_tq) if symbol_after_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',
                }
                month_before = month
                self.env['report.kpi'].sudo().search([]).create(vals)
            elif month == 'Qúy 1':
                data_point = self.env['report.kpi'].sudo().search([
                    ('department_id', '=', self.department_id.id),
                    ('year', '=', self.year)])
                data_point = data_point.filtered(lambda x: x.start_date and 1 <= x.start_date.month <= 3)
                if data_point:
                    # Lọc bỏ các giá trị 0
                    point_after_values = [p for p in data_point.mapped('total_points_after') if p != 0]
                    tq_point_after_values = [p for p in data_point.mapped('tq_total_points_after') if p != 0]

                    point_after = sum(point_after_values) / len(point_after_values) if point_after_values else 0
                    tq_point_after = sum(tq_point_after_values) / len(
                        tq_point_after_values) if tq_point_after_values else 0
                else:
                    point_after = 0
                    tq_point_after = 0

                amount_work, matter_work, comply_regulations, initiative, total = self.get_data_quarter_one(result_month)

                if point_after < 1:
                    symbol_month_before = ""
                    classification = ""
                elif point_after > 100:
                    symbol_month_before = "A1"
                    classification = "Xuất sắc"
                elif point_after > 90:
                    symbol_month_before = "A2"
                    classification = "Tốt"
                elif point_after > 75:
                    symbol_month_before = "A3"
                    classification = "Khá"
                elif point_after > 65:
                    symbol_month_before = "B"
                    classification = "Hoàn thành"
                else:
                    symbol_month_before = "C"
                    classification = "Cần cố gắng"

                amount_work_tq, matter_work_tq, comply_regulations_tq, initiative_tq, total_tq = self.get_data_quarter_one_tq(
                    result_month)

                if tq_point_after < 1:
                    symbol_month_before_tq = ""
                    classification_tq = ""
                elif tq_point_after > 100:
                    symbol_month_before_tq = "A1"
                    classification_tq = "Xuất sắc"
                elif tq_point_after > 90:
                    symbol_month_before_tq = "A2"
                    classification_tq = "Tốt"
                elif tq_point_after > 75:
                    symbol_month_before_tq = "A3"
                    classification_tq = "Khá"
                elif tq_point_after > 65:
                    symbol_month_before_tq = "B"
                    classification_tq = "Hoàn thành"
                else:
                    symbol_month_before_tq = "C"
                    classification_tq = "Cần cố gắng"
                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'month': month + '/' + str(self.year),
                    'workload': round(amount_work, 2) if amount_work else 0,
                    'quality': str(round(matter_work, 2)) if matter_work else '',
                    'discipline': str(round(comply_regulations, 2)) if comply_regulations else '',
                    'improvement': str(round(initiative, 2)) if initiative else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_month_before) if symbol_month_before else '',
                    'progress_points': '',
                    'total_points_after': (round(point_after, 2)) if point_after else '',
                    'symbol_after': str(symbol_month_before) if symbol_month_before else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': (round(amount_work_tq, 2)) if amount_work_tq else 0,
                    'tq_quality': str(round(matter_work_tq, 2)) if matter_work_tq else '',
                    'tq_discipline': str(round(comply_regulations_tq, 2)) if comply_regulations_tq else '',
                    'tq_improvement': str(round(initiative_tq, 2)) if initiative_tq else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_progress_points': '',
                    'tq_total_points_after': (round(tq_point_after, 2)) if tq_point_after else '',
                    'tq_symbol_after': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',

                }
                self.env['report.kpi'].sudo().search([]).create(vals)

            elif month == 'Qúy 2':
                data_point = self.env['report.kpi'].sudo().search([
                    ('department_id', '=', self.department_id.id),
                    ('year', '=', self.year)])
                data_point = data_point.filtered(lambda x: x.start_date and 4 <= x.start_date.month <= 6)
                if data_point:
                    # Lọc bỏ các giá trị 0
                    point_after_values = [p for p in data_point.mapped('total_points_after') if p != 0]
                    tq_point_after_values = [p for p in data_point.mapped('tq_total_points_after') if p != 0]

                    point_after = sum(point_after_values) / len(point_after_values) if point_after_values else 0
                    tq_point_after = sum(tq_point_after_values) / len(
                        tq_point_after_values) if tq_point_after_values else 0
                else:
                    point_after = 0
                    tq_point_after = 0
                amount_work, matter_work, comply_regulations, initiative, total = self.get_data_quarter_two(result_month)
                if point_after < 1:
                    symbol_month_before = ""
                    classification = ""
                elif point_after > 100:
                    symbol_month_before = "A1"
                    classification = "Xuất sắc"
                elif point_after > 90:
                    symbol_month_before = "A2"
                    classification = "Tốt"
                elif point_after > 75:
                    symbol_month_before = "A3"
                    classification = "Khá"
                elif point_after > 65:
                    symbol_month_before = "B"
                    classification = "Hoàn thành"
                else:
                    symbol_month_before = "C"
                    classification = "Cần cố gắng"

                amount_work_tq, matter_work_tq, comply_regulations_tq, initiative_tq, total_tq = self.get_data_quarter_two_tq(
                    result_month)

                if tq_point_after < 1:
                    symbol_month_before_tq = ""
                    classification_tq = ""
                elif tq_point_after > 100:
                    symbol_month_before_tq = "A1"
                    classification_tq = "Xuất sắc"
                elif tq_point_after > 90:
                    symbol_month_before_tq = "A2"
                    classification_tq = "Tốt"
                elif tq_point_after > 75:
                    symbol_month_before_tq = "A3"
                    classification_tq = "Khá"
                elif tq_point_after > 65:
                    symbol_month_before_tq = "B"
                    classification_tq = "Hoàn thành"
                else:
                    symbol_month_before_tq = "C"
                    classification_tq = "Cần cố gắng"
                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'month': month + '/' + str(self.year),
                    'workload': (round(amount_work, 2)) if amount_work else 0,
                    'quality': str(round(matter_work, 2)) if matter_work else '',
                    'discipline': str(round(comply_regulations, 2)) if comply_regulations else '',
                    'improvement': str(round(initiative, 2)) if initiative else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_month_before) if symbol_month_before else '',
                    'progress_points': '',
                    'total_points_after': (round(point_after, 2)) if point_after else '',
                    'symbol_after': str(symbol_month_before) if symbol_month_before else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': (round(amount_work_tq, 2)) if amount_work_tq else 0,
                    'tq_quality': str(round(matter_work_tq, 2)) if matter_work_tq else '',
                    'tq_discipline': str(round(comply_regulations_tq, 2)) if comply_regulations_tq else '',
                    'tq_improvement': str(round(initiative_tq, 2)) if initiative_tq else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_progress_points': '',
                    'tq_total_points_after': (round(tq_point_after, 2)) if tq_point_after else '',
                    'tq_symbol_after': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',

                }
                self.env['report.kpi'].sudo().search([]).create(vals)

            elif month == 'Qúy 3':
                data_point = self.env['report.kpi'].sudo().search([
                    ('department_id', '=', self.department_id.id),
                    ('year', '=', self.year)])
                data_point = data_point.filtered(lambda x: x.start_date and 7 <= x.start_date.month <= 9)
                if data_point:
                    # Lọc bỏ các giá trị 0
                    point_after_values = [p for p in data_point.mapped('total_points_after') if p != 0]
                    tq_point_after_values = [p for p in data_point.mapped('tq_total_points_after') if p != 0]

                    point_after = sum(point_after_values) / len(point_after_values) if point_after_values else 0
                    tq_point_after = sum(tq_point_after_values) / len(
                        tq_point_after_values) if tq_point_after_values else 0
                else:
                    point_after = 0
                    tq_point_after = 0
                amount_work, matter_work, comply_regulations, initiative, total = self.get_data_quarter_three(result_month)
                if point_after < 1:
                    symbol_month_before = ""
                    classification = ""
                elif point_after > 100:
                    symbol_month_before = "A1"
                    classification = "Xuất sắc"
                elif point_after > 90:
                    symbol_month_before = "A2"
                    classification = "Tốt"
                elif point_after > 75:
                    symbol_month_before = "A3"
                    classification = "Khá"
                elif point_after > 65:
                    symbol_month_before = "B"
                    classification = "Hoàn thành"
                else:
                    symbol_month_before = "C"
                    classification = "Cần cố gắng"

                amount_work_tq, matter_work_tq, comply_regulations_tq, initiative_tq, total_tq = self.get_data_quarter_three_tq(
                    result_month)

                if tq_point_after < 1:
                    symbol_month_before_tq = ""
                    classification_tq = ""
                elif tq_point_after > 100:
                    symbol_month_before_tq = "A1"
                    classification_tq = "Xuất sắc"
                elif tq_point_after > 90:
                    symbol_month_before_tq = "A2"
                    classification_tq = "Tốt"
                elif tq_point_after > 75:
                    symbol_month_before_tq = "A3"
                    classification_tq = "Khá"
                elif tq_point_after > 65:
                    symbol_month_before_tq = "B"
                    classification_tq = "Hoàn thành"
                else:
                    symbol_month_before_tq = "C"
                    classification_tq = "Cần cố gắng"
                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'month': month + '/' + str(self.year),
                    'workload': (round(amount_work, 2)) if amount_work else 0,
                    'quality': str(round(matter_work, 2)) if matter_work else '',
                    'discipline': str(round(comply_regulations, 2)) if comply_regulations else '',
                    'improvement': str(round(initiative, 2)) if initiative else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_month_before) if symbol_month_before else '',
                    'progress_points': '',
                    'total_points_after': (round(point_after, 2)) if point_after else '',
                    'symbol_after': str(symbol_month_before) if symbol_month_before else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': (round(amount_work_tq, 2)) if amount_work_tq else 0,
                    'tq_quality': str(round(matter_work_tq, 2)) if matter_work_tq else '',
                    'tq_discipline': str(round(comply_regulations_tq, 2)) if comply_regulations_tq else '',
                    'tq_improvement': str(round(initiative_tq, 2)) if initiative_tq else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_progress_points': '',
                    'tq_total_points_after': (round(tq_point_after, 2)) if tq_point_after else '',
                    'tq_symbol_after': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',

                }
                self.env['report.kpi'].sudo().search([]).create(vals)

            elif month == 'Qúy 4':
                data_point = self.env['report.kpi'].sudo().search([
                    ('department_id', '=', self.department_id.id),
                    ('year', '=', self.year)])
                data_point = data_point.filtered(lambda x: x.start_date and 10 <= x.start_date.month <= 12)
                if data_point:
                    # Lọc bỏ các giá trị 0
                    point_after_values = [p for p in data_point.mapped('total_points_after') if p != 0]
                    tq_point_after_values = [p for p in data_point.mapped('tq_total_points_after') if p != 0]

                    point_after = sum(point_after_values) / len(point_after_values) if point_after_values else 0
                    tq_point_after = sum(tq_point_after_values) / len(
                        tq_point_after_values) if tq_point_after_values else 0
                else:
                    point_after = 0
                    tq_point_after = 0
                amount_work, matter_work, comply_regulations, initiative, total = self.get_data_quarter_four(result_month)
                if point_after < 1:
                    symbol_month_before = ""
                    classification = ""
                elif point_after > 100:
                    symbol_month_before = "A1"
                    classification = "Xuất sắc"
                elif point_after > 90:
                    symbol_month_before = "A2"
                    classification = "Tốt"
                elif point_after > 75:
                    symbol_month_before = "A3"
                    classification = "Khá"
                elif point_after > 65:
                    symbol_month_before = "B"
                    classification = "Hoàn thành"
                else:
                    symbol_month_before = "C"
                    classification = "Cần cố gắng"

                amount_work_tq, matter_work_tq, comply_regulations_tq, initiative_tq, total_tq = self.get_data_quarter_four_tq(
                    result_month)

                if tq_point_after < 1:
                    symbol_month_before_tq = ""
                    classification_tq = ""
                elif tq_point_after > 100:
                    symbol_month_before_tq = "A1"
                    classification_tq = "Xuất sắc"
                elif tq_point_after > 90:
                    symbol_month_before_tq = "A2"
                    classification_tq = "Tốt"
                elif tq_point_after > 75:
                    symbol_month_before_tq = "A3"
                    classification_tq = "Khá"
                elif tq_point_after > 65:
                    symbol_month_before_tq = "B"
                    classification_tq = "Hoàn thành"
                else:
                    symbol_month_before_tq = "C"
                    classification_tq = "Cần cố gắng"
                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'month': month + '/' + str(self.year),
                    'workload': (round(amount_work, 2)) if amount_work else 0,
                    'quality': str(round(matter_work, 2)) if matter_work else '',
                    'discipline': str(round(comply_regulations, 2)) if comply_regulations else '',
                    'improvement': str(round(initiative, 2)) if initiative else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_month_before) if symbol_month_before else '',
                    'progress_points': '',
                    'total_points_after': (round(point_after, 2)) if point_after else '',
                    'symbol_after': str(symbol_month_before) if symbol_month_before else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': (round(amount_work_tq, 2)) if amount_work_tq else 0,
                    'tq_quality': str(round(matter_work_tq, 2)) if matter_work_tq else '',
                    'tq_discipline': str(round(comply_regulations_tq, 2)) if comply_regulations_tq else '',
                    'tq_improvement': str(round(initiative_tq, 2)) if initiative_tq else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_progress_points': '',
                    'tq_total_points_after': (round(tq_point_after, 2)) if tq_point_after else '',
                    'tq_symbol_after': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',

                }
                self.env['report.kpi'].sudo().search([]).create(vals)

            else:
                data_point = self.env['report.kpi'].sudo().search([
                    ('department_id', '=', self.department_id.id),
                    ('year', '=', self.year)])
                if data_point:
                    # Lọc bỏ các giá trị 0
                    point_after_values = [p for p in data_point.mapped('total_points_after') if p != 0]
                    tq_point_after_values = [p for p in data_point.mapped('tq_total_points_after') if p != 0]

                    point_after = sum(point_after_values) / len(point_after_values) if point_after_values else 0
                    tq_point_after = sum(tq_point_after_values) / len(
                        tq_point_after_values) if tq_point_after_values else 0
                else:
                    point_after = 0
                    tq_point_after = 0
                amount_work, matter_work, comply_regulations, initiative, total = self.get_data_year(
                    result_month)
                if point_after < 1:
                    symbol_month_before = ""
                    classification = ""
                elif point_after > 100:
                    symbol_month_before = "A1"
                    classification = "Xuất sắc"
                elif point_after > 90:
                    symbol_month_before = "A2"
                    classification = "Tốt"
                elif point_after > 75:
                    symbol_month_before = "A3"
                    classification = "Khá"
                elif point_after > 65:
                    symbol_month_before = "B"
                    classification = "Hoàn thành"
                else:
                    symbol_month_before = "C"
                    classification = "Cần cố gắng"

                amount_work_tq, matter_work_tq, comply_regulations_tq, initiative_tq, total_tq = self.get_data_year_tq(
                    result_month)

                if tq_point_after < 1:
                    symbol_month_before_tq = ""
                    classification_tq = ""
                elif tq_point_after > 100:
                    symbol_month_before_tq = "A1"
                    classification_tq = "Xuất sắc"
                elif tq_point_after > 90:
                    symbol_month_before_tq = "A2"
                    classification_tq = "Tốt"
                elif tq_point_after > 75:
                    symbol_month_before_tq = "A3"
                    classification_tq = "Khá"
                elif tq_point_after > 65:
                    symbol_month_before_tq = "B"
                    classification_tq = "Hoàn thành"
                else:
                    symbol_month_before_tq = "C"
                    classification_tq = "Cần cố gắng"
                vals = {
                    'department_id': self.department_id.id,
                    'year': self.year,
                    'month': month + '/' + str(self.year),
                    'workload': (round(amount_work, 2)) if amount_work else 0,
                    'quality': str(round(matter_work, 2)) if matter_work else '',
                    'discipline': str(round(comply_regulations, 2)) if comply_regulations else '',
                    'improvement': str(round(initiative, 2)) if initiative else '',
                    'total_points_before': str(round(total, 2)) if total else '',
                    'symbol_before': str(symbol_month_before) if symbol_month_before else '',
                    'progress_points': '',
                    'total_points_after': (round(point_after, 2)) if point_after else '',
                    'symbol_after': str(symbol_month_before) if symbol_month_before else '',
                    'classification': str(classification) if classification else '',
                    'plan': "100%" if classification else '',
                    'criteria_achievement': str(round(total, 2)) + "%" if total else '',

                    'tq_workload': (round(amount_work_tq, 2)) if amount_work_tq else 0,
                    'tq_quality': str(round(matter_work_tq, 2)) if matter_work_tq else '',
                    'tq_discipline': str(round(comply_regulations_tq, 2)) if comply_regulations_tq else '',
                    'tq_improvement': str(round(initiative_tq, 2)) if initiative_tq else '',
                    'tq_total_points_before': str(round(total_tq, 2)) if total_tq else '',
                    'tq_symbol_before': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_progress_points': '',
                    'tq_total_points_after': (round(tq_point_after, 2)) if tq_point_after else '',
                    'tq_symbol_after': str(symbol_month_before_tq) if symbol_month_before_tq else '',
                    'tq_classification': str(classification_tq) if classification_tq else '',
                    'tq_plan': "100%" if classification_tq else '',
                    'tq_criteria_achievement': str(round(total_tq, 2)) + "%" if total_tq else '',

                }
                self.env['report.kpi'].sudo().search([]).create(vals)

    def get_data_year(self, result_month):
        amount_work = []
        matter_work = []
        comply_regulations = []
        initiative = []
        total = []
        amount_work_1, matter_work_1, comply_regulations_1, initiative_1, total_1 = self.get_data_quarter_one(result_month)
        amount_work_2, matter_work_2, comply_regulations_2, initiative_2, total_2 = self.get_data_quarter_two(result_month)
        amount_work_3, matter_work_3, comply_regulations_3, initiative_3, total_3 = self.get_data_quarter_three(result_month)
        amount_work_4, matter_work_4, comply_regulations_4, initiative_4, total_4 = self.get_data_quarter_four(result_month)
        if total_1:
            total.append(total_1)
        if total_2:
            total.append(total_2)
        if total_3:
            total.append(total_3)
        if total_4:
            total.append(total_4)

        if initiative_1:
            initiative.append(initiative_1)
        if initiative_2:
            initiative.append(initiative_2)
        if initiative_3:
            initiative.append(initiative_3)
        if initiative_4:
            initiative.append(initiative_4)

        if comply_regulations_1:
            comply_regulations.append(comply_regulations_1)
        if comply_regulations_2:
            comply_regulations.append(comply_regulations_2)
        if comply_regulations_3:
            comply_regulations.append(comply_regulations_3)
        if comply_regulations_4:
            comply_regulations.append(comply_regulations_4)

        if amount_work_1:
            amount_work.append(amount_work_1)
        if amount_work_2:
            amount_work.append(amount_work_2)
        if amount_work_3:
            amount_work.append(amount_work_3)
        if amount_work_4:
            amount_work.append(amount_work_4)

        if matter_work_1:
            matter_work.append(matter_work_1)
        if matter_work_2:
            matter_work.append(matter_work_2)
        if matter_work_3:
            matter_work.append(matter_work_3)
        if matter_work_4:
            matter_work.append(matter_work_4)

        if len(amount_work) > 0:
            amount_work_t = sum(amount_work) / len(amount_work)
        else:
            amount_work_t = 0

        if len(matter_work) > 0:
            matter_work_t = sum(matter_work) / len(matter_work)
        else:
            matter_work_t = 0

        if len(comply_regulations) > 0:
            comply_regulations_t = sum(comply_regulations) / len(comply_regulations)
        else:
            comply_regulations_t = 0

        if len(initiative) > 0:
            initiative_t = sum(initiative) / len(initiative)
        else:
            initiative_t = 0

        if len(total) > 0:
            total_t = sum(total) / len(total)
        else:
            total_t = 0

        return amount_work_t, matter_work_t, comply_regulations_t, initiative_t, total_t

    def get_data_year_tq(self, result_month):
        amount_work = []
        matter_work = []
        comply_regulations = []
        initiative = []
        total = []
        amount_work_1, matter_work_1, comply_regulations_1, initiative_1, total_1 = self.get_data_quarter_one_tq(
            result_month)
        amount_work_2, matter_work_2, comply_regulations_2, initiative_2, total_2 = self.get_data_quarter_two_tq(
            result_month)
        amount_work_3, matter_work_3, comply_regulations_3, initiative_3, total_3 = self.get_data_quarter_three_tq(
            result_month)
        amount_work_4, matter_work_4, comply_regulations_4, initiative_4, total_4 = self.get_data_quarter_four_tq(
            result_month)
        if total_1:
            total.append(total_1)
        if total_2:
            total.append(total_2)
        if total_3:
            total.append(total_3)
        if total_4:
            total.append(total_4)

        if initiative_1:
            initiative.append(initiative_1)
        if initiative_2:
            initiative.append(initiative_2)
        if initiative_3:
            initiative.append(initiative_3)
        if initiative_4:
            initiative.append(initiative_4)

        if comply_regulations_1:
            comply_regulations.append(comply_regulations_1)
        if comply_regulations_2:
            comply_regulations.append(comply_regulations_2)
        if comply_regulations_3:
            comply_regulations.append(comply_regulations_3)
        if comply_regulations_4:
            comply_regulations.append(comply_regulations_4)

        if amount_work_1:
            amount_work.append(amount_work_1)
        if amount_work_2:
            amount_work.append(amount_work_2)
        if amount_work_3:
            amount_work.append(amount_work_3)
        if amount_work_4:
            amount_work.append(amount_work_4)

        if matter_work_1:
            matter_work.append(matter_work_1)
        if matter_work_2:
            matter_work.append(matter_work_2)
        if matter_work_3:
            matter_work.append(matter_work_3)
        if matter_work_4:
            matter_work.append(matter_work_4)

        if len(amount_work) > 0:
            amount_work_t = sum(amount_work) / len(amount_work)
        else:
            amount_work_t = 0

        if len(matter_work) > 0:
            matter_work_t = sum(matter_work) / len(matter_work)
        else:
            matter_work_t = 0

        if len(comply_regulations) > 0:
            comply_regulations_t = sum(comply_regulations) / len(comply_regulations)
        else:
            comply_regulations_t = 0

        if len(initiative) > 0:
            initiative_t = sum(initiative) / len(initiative)
        else:
            initiative_t = 0

        if len(total) > 0:
            total_t = sum(total) / len(total)
        else:
            total_t = 0

        return amount_work_t, matter_work_t, comply_regulations_t, initiative_t, total_t

    def get_data_quarter_one_tq(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 1)
        month_two = result_month.filtered(lambda x: x.start_date.month == 2)
        month_three = result_month.filtered(lambda x: x.start_date.month == 3)
        if month_one:
            if sum(month_one.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_tq_amount_work')))
            if sum(month_one.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_tq_matter_work')))
            if sum(month_one.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_one.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_tq_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_tq_amount_work')))
            if sum(month_two.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_tq_matter_work')))
            if sum(month_two.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_two.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_tq_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_tq_amount_work')))
            if sum(month_three.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_tq_matter_work')))
            if sum(month_three.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_three.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_tq_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_two_tq(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 4)
        month_two = result_month.filtered(lambda x: x.start_date.month == 5)
        month_three = result_month.filtered(lambda x: x.start_date.month == 6)
        if month_one:
            if sum(month_one.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_tq_amount_work')))
            if sum(month_one.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_tq_matter_work')))
            if sum(month_one.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_one.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_tq_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_tq_amount_work')))
            if sum(month_two.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_tq_matter_work')))
            if sum(month_two.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_two.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_tq_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_tq_amount_work')))
            if sum(month_three.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_tq_matter_work')))
            if sum(month_three.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_three.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_tq_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_three_tq(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 7)
        month_two = result_month.filtered(lambda x: x.start_date.month == 8)
        month_three = result_month.filtered(lambda x: x.start_date.month == 9)
        if month_one:
            if sum(month_one.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_tq_amount_work')))
            if sum(month_one.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_tq_matter_work')))
            if sum(month_one.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_one.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_tq_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_tq_amount_work')))
            if sum(month_two.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_tq_matter_work')))
            if sum(month_two.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_two.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_tq_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_tq_amount_work')))
            if sum(month_three.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_tq_matter_work')))
            if sum(month_three.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_three.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_tq_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_four_tq(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 10)
        month_two = result_month.filtered(lambda x: x.start_date.month == 11)
        month_three = result_month.filtered(lambda x: x.start_date.month == 12)
        if month_one:
            if sum(month_one.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_tq_amount_work')))
            if sum(month_one.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_tq_matter_work')))
            if sum(month_one.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_one.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_tq_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_tq_amount_work')))
            if sum(month_two.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_tq_matter_work')))
            if sum(month_two.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_two.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_tq_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_tq_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_tq_amount_work')))
            if sum(month_three.mapped('quy_doi_tq_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_tq_matter_work')))
            if sum(month_three.mapped('quy_doi_tq_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_tq_comply_regulations')))
            if sum(month_three.mapped('quy_doi_tq_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_tq_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_one(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 1)
        month_two = result_month.filtered(lambda x: x.start_date.month == 2)
        month_three = result_month.filtered(lambda x: x.start_date.month == 3)
        if month_one:
            if sum(month_one.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_dv_amount_work')))
            if sum(month_one.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_dv_matter_work')))
            if sum(month_one.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_one.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_dv_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_dv_amount_work')))
            if sum(month_two.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_dv_matter_work')))
            if sum(month_two.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_two.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_dv_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_dv_amount_work')))
            if sum(month_three.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_dv_matter_work')))
            if sum(month_three.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_three.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_dv_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_two(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 4)
        month_two = result_month.filtered(lambda x: x.start_date.month == 5)
        month_three = result_month.filtered(lambda x: x.start_date.month == 6)
        if month_one:
            if sum(month_one.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_dv_amount_work')))
            if sum(month_one.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_dv_matter_work')))
            if sum(month_one.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_one.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_dv_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_dv_amount_work')))
            if sum(month_two.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_dv_matter_work')))
            if sum(month_two.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_two.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_dv_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_dv_amount_work')))
            if sum(month_three.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_dv_matter_work')))
            if sum(month_three.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_three.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_dv_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative
        if total < 1:
            symbol_month_before = ""
        elif total > 100:
            symbol_month_before = "A1"
        elif total > 90:
            symbol_month_before = "A2"
        elif total > 75:
            symbol_month_before = "A3"
        elif total > 65:
            symbol_month_before = "B"
        else:
            symbol_month_before = "C"

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_three(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 7)
        month_two = result_month.filtered(lambda x: x.start_date.month == 8)
        month_three = result_month.filtered(lambda x: x.start_date.month == 9)
        if month_one:
            if sum(month_one.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_dv_amount_work')))
            if sum(month_one.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_dv_matter_work')))
            if sum(month_one.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_one.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_dv_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_dv_amount_work')))
            if sum(month_two.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_dv_matter_work')))
            if sum(month_two.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_two.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_dv_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_dv_amount_work')))
            if sum(month_three.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_dv_matter_work')))
            if sum(month_three.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_three.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_dv_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative
        if total < 1:
            symbol_month_before = ""
        elif total > 100:
            symbol_month_before = "A1"
        elif total > 90:
            symbol_month_before = "A2"
        elif total > 75:
            symbol_month_before = "A3"
        elif total > 65:
            symbol_month_before = "B"
        else:
            symbol_month_before = "C"

        return amount_work, matter_work, comply_regulations, initiative, total

    def get_data_quarter_four(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 10)
        month_two = result_month.filtered(lambda x: x.start_date.month == 11)
        month_three = result_month.filtered(lambda x: x.start_date.month == 12)
        if month_one:
            if sum(month_one.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_dv_amount_work')))
            if sum(month_one.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_dv_matter_work')))
            if sum(month_one.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_one.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_dv_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_dv_amount_work')))
            if sum(month_two.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_dv_matter_work')))
            if sum(month_two.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_two.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_dv_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_dv_amount_work')))
            if sum(month_three.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_dv_matter_work')))
            if sum(month_three.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_three.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_dv_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative
        if total < 1:
            symbol_month_before = ""
        elif total > 100:
            symbol_month_before = "A1"
        elif total > 90:
            symbol_month_before = "A2"
        elif total > 75:
            symbol_month_before = "A3"
        elif total > 65:
            symbol_month_before = "B"
        else:
            symbol_month_before = "C"

        return amount_work, matter_work, comply_regulations, initiative, total

    def calculate_classification_and_points_authorization(self, data_filter, data_before):
        workload = round(sum(data_filter.mapped('quy_doi_tq_amount_work')), 2) if data_filter else 0
        quality = round(sum(data_filter.mapped('quy_doi_tq_matter_work')), 2) if data_filter else 0
        discipline = round(sum(data_filter.mapped('quy_doi_tq_comply_regulations')), 2) if data_filter else 0
        improvement = round(sum(data_filter.mapped('quy_doi_tq_initiative')), 2) if data_filter else 0
        total = workload + quality + discipline + improvement

        workload_before = round(sum(data_before.mapped('quy_doi_tq_amount_work')), 2) if data_before else 0
        quality_before = round(sum(data_before.mapped('quy_doi_tq_matter_work')), 2) if data_before else 0
        discipline_before = round(sum(data_before.mapped('quy_doi_tq_comply_regulations')), 2) if data_before else 0
        improvement_before = round(sum(data_before.mapped('quy_doi_tq_initiative')), 2) if data_before else 0
        total_before = workload_before + quality_before + discipline_before + improvement_before

        rating_table = {
            'A1': {'A1': 0, 'A2': -5, 'A3': -10, 'B': -15, 'C': -20},
            'A2': {'A1': 5, 'A2': 0, 'A3': -5, 'B': -10, 'C': -15},
            'A3': {'A1': 10, 'A2': 5, 'A3': 0, 'B': -5, 'C': -10},
            'B': {'A1': 15, 'A2': 10, 'A3': 5, 'B': 0, 'C': -5},
            'C': {'A1': 20, 'A2': 15, 'A3': 10, 'B': 5, 'C': 0},
        }
        if total_before < 1:
            symbol_month_before = ""
        elif total_before > 100:
            symbol_month_before = "A1"
        elif total_before > 90:
            symbol_month_before = "A2"
        elif total_before > 75:
            symbol_month_before = "A3"
        elif total_before > 65:
            symbol_month_before = "B"
        else:
            symbol_month_before = "C"

        if total < 1:
            symbol_before = ""
        elif total > 100:
            symbol_before = "A1"
        elif total > 90:
            symbol_before = "A2"
        elif total > 75:
            symbol_before = "A3"
        elif total > 65:
            symbol_before = "B"
        else:
            symbol_before = "C"

        if symbol_month_before and symbol_before:
            progress_points = rating_table.get(symbol_month_before, {}).get(symbol_before, 0)
        else:
            progress_points = 0

        total_points_after = total + progress_points

        if total_points_after < 1:
            symbol_after = ""
            classification = ""
        elif total_points_after > 100:
            symbol_after = "A1"
            classification = "Xuất sắc"
        elif total_points_after > 90:
            symbol_after = "A2"
            classification = "Tốt"
        elif total_points_after > 75:
            symbol_after = "A3"
            classification = "Khá"
        elif total_points_after > 65:
            symbol_after = "B"
            classification = "Hoàn thành"
        else:
            symbol_after = "C"
            classification = "Cần cố gắng"

        return total, symbol_before, total_points_after, symbol_after, classification, progress_points

    def calculate_classification_and_points(self, data_filter, data_before):
        workload = round(sum(data_filter.mapped('quy_doi_dv_amount_work')), 2) if data_filter else 0
        quality = round(sum(data_filter.mapped('quy_doi_dv_matter_work')), 2) if data_filter else 0
        discipline = round(sum(data_filter.mapped('quy_doi_dv_comply_regulations')), 2) if data_filter else 0
        improvement = round(sum(data_filter.mapped('quy_doi_dv_initiative')), 2) if data_filter else 0
        total = workload + quality + discipline + improvement

        workload_before = round(sum(data_before.mapped('quy_doi_dv_amount_work')), 2) if data_before else 0
        quality_before = round(sum(data_before.mapped('quy_doi_dv_matter_work')), 2) if data_before else 0
        discipline_before = round(sum(data_before.mapped('quy_doi_dv_comply_regulations')), 2) if data_before else 0
        improvement_before = round(sum(data_before.mapped('quy_doi_dv_initiative')), 2) if data_before else 0
        total_before = workload_before + quality_before + discipline_before + improvement_before

        rating_table = {
            'A1': {'A1': 0, 'A2': -5, 'A3': -10, 'B': -15, 'C': -20},
            'A2': {'A1': 5, 'A2': 0, 'A3': -5, 'B': -10, 'C': -15},
            'A3': {'A1': 10, 'A2': 5, 'A3': 0, 'B': -5, 'C': -10},
            'B': {'A1': 15, 'A2': 10, 'A3': 5, 'B': 0, 'C': -5},
            'C': {'A1': 20, 'A2': 15, 'A3': 10, 'B': 5, 'C': 0},
        }
        if total_before < 1:
            symbol_month_before = ""
        elif total_before > 100:
            symbol_month_before = "A1"
        elif total_before > 90:
            symbol_month_before = "A2"
        elif total_before > 75:
            symbol_month_before = "A3"
        elif total_before > 65:
            symbol_month_before = "B"
        else:
            symbol_month_before = "C"

        if total < 1:
            symbol_before = ""
        elif total > 100:
            symbol_before = "A1"
        elif total > 90:
            symbol_before = "A2"
        elif total > 75:
            symbol_before = "A3"
        elif total > 65:
            symbol_before = "B"
        else:
            symbol_before = "C"

        if symbol_month_before and symbol_before:
            progress_points = rating_table.get(symbol_month_before, {}).get(symbol_before, 0)
        else:
            progress_points = 0

        total_points_after = total + progress_points

        if total_points_after < 1:
            symbol_after = ""
            classification = ""
        elif total_points_after > 100:
            symbol_after = "A1"
            classification = "Xuất sắc"
        elif total_points_after > 90:
            symbol_after = "A2"
            classification = "Tốt"
        elif total_points_after > 75:
            symbol_after = "A3"
            classification = "Khá"
        elif total_points_after > 65:
            symbol_after = "B"
            classification = "Hoàn thành"
        else:
            symbol_after = "C"
            classification = "Cần cố gắng"

        return total, symbol_before, total_points_after, symbol_after, classification, progress_points

    def get_data_quarter_one(self, result_month):
        number_amount_work = []
        number_matter_work = []
        number_comply_regulations = []
        number_initiative = []
        month_one = result_month.filtered(lambda x: x.start_date.month == 1)
        month_two = result_month.filtered(lambda x: x.start_date.month == 2)
        month_three = result_month.filtered(lambda x: x.start_date.month == 3)
        if month_one:
            if sum(month_one.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_one.mapped('quy_doi_dv_amount_work')))
            if sum(month_one.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_one.mapped('quy_doi_dv_matter_work')))
            if sum(month_one.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_one.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_one.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_one.mapped('quy_doi_dv_initiative')))
        if month_two:
            if sum(month_two.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_two.mapped('quy_doi_dv_amount_work')))
            if sum(month_two.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_two.mapped('quy_doi_dv_matter_work')))
            if sum(month_two.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_two.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_two.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_two.mapped('quy_doi_dv_initiative')))
        if month_three:
            if sum(month_three.mapped('quy_doi_dv_amount_work')) > 0:
                number_amount_work.append(sum(month_three.mapped('quy_doi_dv_amount_work')))
            if sum(month_three.mapped('quy_doi_dv_matter_work')) > 0:
                number_matter_work.append(sum(month_three.mapped('quy_doi_dv_matter_work')))
            if sum(month_three.mapped('quy_doi_dv_comply_regulations')) > 0:
                number_comply_regulations.append(sum(month_three.mapped('quy_doi_dv_comply_regulations')))
            if sum(month_three.mapped('quy_doi_dv_initiative')) > 0:
                number_initiative.append(sum(month_three.mapped('quy_doi_dv_initiative')))
        if len(number_amount_work) > 0:
            amount_work = sum(number_amount_work) / len(number_amount_work)
        else:
            amount_work = 0

        if len(number_matter_work) > 0:
            matter_work = sum(number_matter_work) / len(number_matter_work)
        else:
            matter_work = 0

        if len(number_comply_regulations) > 0:
            comply_regulations = sum(number_comply_regulations) / len(number_comply_regulations)
        else:
            comply_regulations = 0

        if len(number_initiative) > 0:
            initiative = sum(number_initiative) / len(number_initiative)
        else:
            initiative = 0

        total = amount_work + matter_work + comply_regulations + initiative

        return amount_work, matter_work, comply_regulations, initiative, total

    def filter_data(self, month, result_month):
        if month == '01':
            return result_month.filtered(lambda x: x.start_date.month == 1)
        elif month == '02':
            return result_month.filtered(lambda x: x.start_date.month == 2)
        elif month == '03':
            return result_month.filtered(lambda x: x.start_date.month == 3)
        elif month == '04':
            return result_month.filtered(lambda x: x.start_date.month == 4)
        elif month == '05':
            return result_month.filtered(lambda x: x.start_date.month == 5)
        elif month == '06':
            return result_month.filtered(lambda x: x.start_date.month == 6)
        elif month == '07':
            return result_month.filtered(lambda x: x.start_date.month == 7)
        elif month == '08':
            return result_month.filtered(lambda x: x.start_date.month == 8)
        elif month == '09':
            return result_month.filtered(lambda x: x.start_date.month == 9)
        elif month == '10':
            return result_month.filtered(lambda x: x.start_date.month == 10)
        elif month == '11':
            return result_month.filtered(lambda x: x.start_date.month == 11)
        elif month == '12':
            return result_month.filtered(lambda x: x.start_date.month == 12)
        elif month == 'Cả năm':
            return result_month
        elif month == 'Qúy 1':
            return result_month.filtered(lambda x: x.start_date.month in [1, 2, 3])
        elif month == 'Qúy 2':
            return result_month.filtered(lambda x: x.start_date.month in [4, 5, 6])
        elif month == 'Qúy 3':
            return result_month.filtered(lambda x: x.start_date.month in [7, 8, 9])
        elif month == 'Qúy 4':
            return result_month.filtered(lambda x: x.start_date.month in [10, 11, 12])
