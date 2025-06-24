from odoo import http
from odoo.http import request
from datetime import datetime
from dateutil.relativedelta import relativedelta
import xlsxwriter
import base64
from io import BytesIO

import json


class DataChart(http.Controller):

    @http.route("/check_method_get", auth='none', type='http', method=['GET'])
    def check_method_get(self, **values):
        department_id = values.get('department_id')
        start_date = values.get('start_date')
        end_date = values.get('end_date')

        # Filter departments based on the department_id parameter
        if department_id:
            department_ids = request.env['hr.department'].sudo().search([('id', '=', int(department_id))])
        else:
            department_ids = request.env['hr.department'].sudo().search([])

        data = []
        for department_id in department_ids:
            complete, unfulfilled, processing = self.get_data_progress(department_id)
            rating_amount = self.rating_amount_work_performed(department_id)
            kpi_plan, kpi_perform = self.kpi_amount(department_id)
            amount, matter, regulations, initiative, progress_points, total = self.criteria_points(department_id)
            result_amount = self.result_amount(department_id)
            data.append({
                'department': department_id.name,
                'complete': round(complete, 2),
                'unfulfilled': round(unfulfilled, 2),
                'processing': round(processing, 2),
                'rating_amount': round(rating_amount, 2),
                'kpi_plan': round(kpi_plan, 2),
                'kpi_th': round(kpi_perform, 2),
                'amount': round(amount, 2),
                'matter': round(matter, 2),
                'regulations': round(regulations, 2),
                'initiative': round(initiative, 2),
                'progress_points': round(progress_points, 2),
                'total': round(total, 2),
                'result_amount': round(result_amount, 2),
            })
        return json.dumps(data)

    @http.route("/get_departments", auth='none', type='http', method=['GET'])
    def get_departments(self, **values):
        departments = request.env['hr.department'].sudo().search([])
        data = [{'id': dept.id, 'name': dept.name} for dept in departments]
        return json.dumps(data)

    def get_data_progress(self, department_id):
        complete = 0
        unfulfilled = 0
        processing = 0
        data = request.env['sonha.kpi.year'].sudo().search([('department_id', '=', department_id.id)])
        data_dang_th = data.filtered(lambda x: x.dvdg_status == 'in_progres')
        data_ht = data.filtered(lambda x: x.dvdg_status == 'done')
        data_chua_th = data.filtered(lambda x: x.dvdg_status == 'draft')
        if data_ht:
            complete = sum(data_ht.mapped('dvdg_kpi')) * 100
        if data_dang_th:
            processing = sum(data_dang_th.mapped('dvdg_kpi')) * 100
        if data_chua_th:
            unfulfilled = 100 - complete - processing
        return complete, unfulfilled, processing

    def rating_amount_work_performed(self, department_id):
        data = request.env['sonha.kpi.month'].sudo().search([('department_id', '=', department_id.id)]).mapped('dv_amount_work')
        rating_amount = 0
        if data:
            rating_amount = (sum(data) / len(data)) * 100
        return rating_amount

    def kpi_amount(self, department_id):
        kpi_plan = 0
        kpi_perform = 0
        data_plan = request.env['sonha.kpi.year'].sudo().search([('department_id', '=', department_id.id)]).mapped('kpi_year')
        data_perform = request.env['sonha.kpi.year'].sudo().search([('department_id', '=', department_id.id)]).mapped('dvdg_kpi')
        if data_plan:
            kpi_plan = (sum(data_plan) / len(data_plan)) * 100
        if data_perform:
            kpi_perform = (sum(data_perform) / len(data_perform)) * 100
        return kpi_plan, kpi_perform

    def criteria_points(self, department_id):
        amount = 0
        matter = 0
        regulations = 0
        initiative = 0
        progress_points = 0

        data_amount = request.env['sonha.kpi.result.month'].sudo().search(
            [('department_id', '=', department_id.id)]).mapped('diem_dat_dv_amount_work')
        data_matter = request.env['sonha.kpi.result.month'].sudo().search(
            [('department_id', '=', department_id.id)]).mapped('diem_dat_dv_matter_work')
        data_regulations = request.env['sonha.kpi.result.month'].sudo().search(
            [('department_id', '=', department_id.id)]).mapped('diem_dat_dv_comply_regulations')
        data_initiative = request.env['sonha.kpi.result.month'].sudo().search(
            [('department_id', '=', department_id.id)]).mapped('diem_dat_dv_initiative')
        if data_amount:
            amount = sum(data_amount) / len(data_amount)
        if data_matter:
            matter = sum(data_matter) / len(data_matter)
        if data_regulations:
            regulations = sum(data_regulations) / len(data_regulations)
        if data_initiative:
            initiative = sum(data_initiative) / len(data_initiative)
        total = amount + matter + regulations + initiative
        return amount, matter, regulations, initiative, progress_points, total

    def calculate_tq_classification(self, data_filter, data_before):
        workload = sum(data_filter.mapped('quy_doi_tq_amount_work')) if data_filter else 0
        quality = sum(data_filter.mapped('quy_doi_tq_matter_work')) if data_filter else 0
        discipline = sum(data_filter.mapped('quy_doi_tq_comply_regulations')) if data_filter else 0
        improvement = sum(data_filter.mapped('quy_doi_tq_initiative')) if data_filter else 0
        total = workload + quality + discipline + improvement

        workload_before = sum(data_before.mapped('quy_doi_tq_amount_work')) if data_before else 0
        quality_before = sum(data_before.mapped('quy_doi_tq_matter_work')) if data_before else 0
        discipline_before = sum(data_before.mapped('quy_doi_tq_comply_regulations')) if data_before else 0
        improvement_before = sum(data_before.mapped('quy_doi_tq_initiative')) if data_before else 0
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
            classification = ""
        elif total_points_after > 100:
            classification = "Xuất sắc"
        elif total_points_after > 90:
            classification = "Tốt"
        elif total_points_after > 75:
            classification = "Khá"
        elif total_points_after > 65:
            classification = "Hoàn thành"
        else:
            classification = "Cần cố gắng"

        return classification

    def calculate_dv_classification(self, data_filter, data_before):
        workload = sum(data_filter.mapped('quy_doi_dv_amount_work')) if data_filter else 0
        quality = sum(data_filter.mapped('quy_doi_dv_matter_work')) if data_filter else 0
        discipline = sum(data_filter.mapped('quy_doi_dv_comply_regulations')) if data_filter else 0
        improvement = sum(data_filter.mapped('quy_doi_dv_initiative')) if data_filter else 0
        total = workload + quality + discipline + improvement

        workload_before = sum(data_before.mapped('quy_doi_dv_amount_work')) if data_before else 0
        quality_before = sum(data_before.mapped('quy_doi_dv_matter_work')) if data_before else 0
        discipline_before = sum(data_before.mapped('quy_doi_dv_comply_regulations')) if data_before else 0
        improvement_before = sum(data_before.mapped('quy_doi_dv_initiative')) if data_before else 0
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
            classification = ""
        elif total_points_after > 100:
            classification = "Xuất sắc"
        elif total_points_after > 90:
            classification = "Tốt"
        elif total_points_after > 75:
            classification = "Khá"
        elif total_points_after > 65:
            classification = "Hoàn thành"
        else:
            classification = "Cần cố gắng"

        return classification


    def result_amount(self,department_id):
        result_amount = 0
        data_result_amount = request.env['sonha.kpi.result.month'].sudo().search(
            [('department_id', '=', department_id.id)]).mapped('kq_hoan_thanh_amount_work')
        if data_result_amount:
            result_amount = (sum(data_result_amount) / len(data_result_amount)) * 100
        return result_amount

    @http.route('/kpi/form', type='http', auth='public', website=True)
    def kpi_form(self, **kwargs):
        department_id = int(kwargs.get('department_id')) if kwargs.get('department_id') else None
        month = int(kwargs.get('month')) if kwargs.get('month') else None
        year = int(kwargs.get('year')) if kwargs.get('year') else None
        month_before = month - 1 if month else None
        manager = request.env['report.mail.to'].sudo().search([('department_id', '=', department_id)]).receive_emp
        if request.env.user.has_group('sonha_employee.group_hr_employee') or manager.user_id.id == request.env.user.id:
            result_records = request.env['sonha.kpi.result.month'].sudo().search([('department_id', '=', department_id),
                                                                                  ('year', '=', year)])
            kpi_records = request.env['report.kpi.month'].sudo().search([('department_id', '=', department_id),
                                                                        ('year', '=', year)])
            if month:
                kpi_records = kpi_records.filtered(lambda x: x.start_date.month == month)
                result_month_records = result_records.filtered(lambda x: x.start_date.month == month)
                result_month_before_records = result_records.filtered(lambda x: x.start_date.month == month_before)
            if result_records:
                dv_classification = self.calculate_dv_classification(result_month_records, result_month_before_records)
                tq_classification = self.calculate_tq_classification(result_month_records, result_month_before_records)
            if kpi_records:
                start_date = datetime.strptime(str(kpi_records[0].start_date), '%Y-%m-%d')
                end_date = datetime.strptime(str(kpi_records[0].end_date), '%Y-%m-%d')
                start_date = start_date.strftime('%d/%m/%Y')
                end_date = end_date.strftime('%d/%m/%Y')
                check_hr_approve = 1 if request.env.user.has_group('sonha_employee.group_hr_employee') and kpi_records[0].status == 'draft' else 0
                check_manager_approve = 1 if manager.user_id.id == request.env.user.id and kpi_records[0].status == 'waiting' else 0
                check_manager_complete = 1 if manager.user_id.id == request.env.user.id and kpi_records[0].status == 'approved' else 0
                return request.render('sonha_kpi.report_kpi_month_rel_template', {
                    'kpi_records': kpi_records,
                    'converted_start_date': start_date,
                    'converted_end_date': end_date,
                    'dv_classification': dv_classification,
                    'tq_classification': tq_classification,
                    'check_hr_approve': check_hr_approve,
                    'check_manager_approve': check_manager_approve,
                    'check_manager_complete': check_manager_complete,
                })
            else:
                return "Chưa có dữ liệu đánh giá!"
        else:
            return "Không có quyền truy cập vào trang này!"


    @http.route('/kpi/update_ajax', type='json', auth='user', methods=['POST'], csrf=False)
    def update_kpi_ajax(self, **kwargs):
        data = request.httprequest.get_json()
        for item in data["kpi_data"]:
            kpi_id = int(item["kpi_id"])
            field_name = item["field_name"]
            field_value = item["field_value"]
            view_field_value = field_value
            if field_name != "tq_description":
                if field_value and float(field_value) >= 0:
                    convert_field = float(field_value)
                    field_value = convert_field / 100
                else:
                    view_field_value = 0
                    field_value = 0
            kpi_record = request.env['sonha.kpi.month'].sudo().search([('id', '=', kpi_id)])
            kpi_report_month = request.env['report.kpi.month'].sudo().search([('small_items_each_month.id', '=', kpi_id)])
            if kpi_record and field_name:
                kpi_record.sudo().write({field_name: field_value})
                kpi_report_month.sudo().write({field_name: view_field_value})

    @http.route('/kpi/kpi_approve', type='json', auth='user', csrf=False)
    def update_kpi_form_status(self):
        data = request.httprequest.get_json()
        for item in data["approve_data"]:
            kpi_id = int(item["kpi_id"])
            field_name = item["field_name"]
            field_value = item["field_value"]
            view_field_value = field_value
            if field_name != "tq_description":
                if field_value and float(field_value) >= 0:
                    convert_field = float(field_value)
                    field_value = convert_field / 100
                else:
                    view_field_value = 0
                    field_value = 0
            kpi_record = request.env['sonha.kpi.month'].sudo().search([('id', '=', kpi_id)])
            kpi_report_month = request.env['report.kpi.month'].sudo().search(
                [('small_items_each_month.id', '=', kpi_id)])
            if kpi_record and field_name:
                kpi_record.sudo().write({field_name: field_value})
                kpi_report_month.sudo().write({field_name: view_field_value})
            if kpi_report_month.status == 'waiting':
                kpi_report_month.sudo().write({'status': 'approved'})

    @http.route('/kpi/hr_approved', type='json', auth='user', csrf=False)
    def hr_approved(self):
        data = request.httprequest.get_json()
        department_id = int(data["department_id"])
        date = data["date"]
        if request.env.user.has_group('sonha_employee.group_hr_employee'):
            month = datetime.strptime(date, '%Y-%m-%d').month
            year = int(datetime.strptime(date, '%Y-%m-%d').year)
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            mail_url = f"{base_url}/kpi/form?department_id={department_id}&month={month}&year={year}"
            now = datetime.now().date()
            kpi_records = request.env['report.kpi.month'].sudo().search([('department_id', '=', department_id),
                                                                        ('year', '=', year)])
            if month:
                kpi_records = kpi_records.filtered(lambda x: x.start_date.month == month)
            for record in kpi_records:
                record.sudo().write({'url_data_mail': mail_url,
                                    'mail_turn': '1',
                                    'status': 'waiting',
                                    'first_mail_date': now})
            mail_to = request.env['report.mail.to'].sudo().search([('department_id.id', '=', kpi_records[0].department_id.id)]).receive_emp.work_email
            cc_emp = request.env['report.mail.to'].sudo().search([('department_id.id', '=', kpi_records[0].department_id.id)])
            if cc_emp:
                cc_emails = ', '.join(emp.work_email for emp in cc_emp.cc_to if emp.work_email)
            if mail_to:
                template_id = request.env.ref('sonha_kpi.report_kpi_mail_template').sudo()
                if template_id:
                    template_id.email_to = mail_to
                    template_id.email_cc = cc_emails
                    template_id.sudo().send_mail(kpi_records[0].id, force_send=True)

    @http.route('/kpi/cancel_kpi_approval', type='json', auth='user', csrf=False)
    def update_cancel_approval(self):
        data = request.httprequest.get_json()
        now = datetime.now().date()
        department_id = int(data["department_id"])
        date = data["date"]
        month = datetime.strptime(date, '%Y-%m-%d').month
        year = int(datetime.strptime(date, '%Y-%m-%d').year)
        kpi_report = request.env['report.kpi.month'].sudo().search([('department_id', '=', department_id),
                                                                    ('year', '=', year)])
        if month:
            kpi_report = kpi_report.filtered(lambda x: x.start_date.month == month)
        if kpi_report:
            for r in kpi_report:
                if r.status == 'approved':
                    r.sudo().write({'status': 'waiting'})

    @http.route('/kpi_next_month/approve', type='http', auth='public', website=True)
    def kpi_next_month_approve(self, **kwargs):
        department_id = int(kwargs.get('department_id')) if kwargs.get('department_id') else None
        month = int(kwargs.get('month')) if kwargs.get('month') else None
        year = int(kwargs.get('year')) if kwargs.get('year') else None
        manager = request.env['report.mail.to'].sudo().search([('department_id', '=', department_id)]).receive_emp
        if manager.user_id.id == request.env.user.id:
            kpi_records = request.env['parent.kpi.month'].sudo().search([('department_id', '=', department_id),
                                                                        ('year', '=', year)])
            if month:
                kpi_records = kpi_records.plan_kpi_month.filtered(lambda x: x.start_date.month == month)
            if kpi_records:
                start_date = datetime.strptime(str(kpi_records[0].start_date), '%Y-%m-%d')
                end_date = datetime.strptime(str(kpi_records[0].end_date), '%Y-%m-%d')
                start_date = start_date.strftime('%d/%m/%Y')
                end_date = end_date.strftime('%d/%m/%Y')
                return request.render('sonha_kpi.approve_plan_month_template', {
                    'kpi_records': kpi_records,
                    'converted_start_date': start_date,
                    'converted_end_date': end_date
                })
            else:
                return "Chưa có dữ liệu của tháng!"
        else:
            return "Bạn không có quyền truy cập màn hình này!"

    @http.route('/kpi/approve_next_month', type='http', auth='none', csrf=False)
    def approve_next_month(self):
        data = request.httprequest.get_json()
        for item in data["next_month"]:
            department_id = int(item["department_id"])
            date = item["date"]
            date = datetime.strptime(date, '%Y-%m-%d')
            next_month_date = date + relativedelta(months=1)
            month = next_month_date.month
            year = next_month_date.year
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            url = f"{base_url}/kpi_next_month/approve?department_id={department_id}&month={month}&year={year}"
        return json.dumps({'status': 'success', 'redirect_url': url})

    @http.route('/kpi_next_month/approve_kpi_month', type='json', auth='none', csrf=False)
    def approve_kpi_next_month(self):
        data = request.httprequest.get_json()
        for item in data["kpi_data"]:
            kpi_year = int(item["kpi_year"])
            kpi_month = item["kpi_month"]
            start_date = item["start_date"]
            end_date = item["end_date"]
            sonha_kpi = int(item["sonha_kpi"])
            department_id = int(item["department_id"])
            parent_kpi_month = int(item["parent_kpi_month"])
            start_date_time = datetime.strptime(start_date, '%d/%m/%Y')
            end_date_time = datetime.strptime(end_date, '%d/%m/%Y')
            start_date = start_date_time.strftime('%Y-%m-%d')
            end_date = end_date_time.strftime('%Y-%m-%d')
            year = start_date_time.year
            parent_plan_kpi = request.env['parent.kpi.month'].sudo().search([('id', '=', parent_kpi_month)])
            if parent_plan_kpi:
                for kpi in parent_plan_kpi:
                    kpi.sudo().write({'status': 'done'})
            request.env['sonha.kpi.month'].sudo().create({
                'department_id': department_id,
                'year': year,
                'kpi_year_id': kpi_year,
                'start_date': f'{start_date}',
                'end_date': f'{end_date}',
                'small_items_each_month': kpi_month,
                'sonha_kpi': sonha_kpi,
                'parent_kpi_month': parent_kpi_month
            })

    @http.route('/kpi_next_month/cancel_approve_kpi_month', type='json', auth='none', csrf=False)
    def cancel_approve_next_month(self):
        data = request.httprequest.get_json()
        date = data["date"]
        sonha_kpi = int(data["sonha_kpi"])
        parent_plan_month = int(data["parent_plan_month"])
        month = datetime.strptime(date, '%d/%m/%Y').month
        company_kpi = request.env['sonha.kpi.month'].sudo().search([('sonha_kpi', '=', sonha_kpi)])
        if month:
            company_kpi_month = company_kpi.filtered(lambda x: x.start_date.month == month)
        if company_kpi_month:
            company_kpi_month.sudo().unlink()
        parent_kpi_month = request.env['parent.kpi.month'].sudo().search([('id', '=', parent_plan_month)])
        if parent_kpi_month:
            for kpi in parent_kpi_month:
                if kpi.status == 'done':
                    kpi.sudo().write({'status': 'draft'})

    @http.route(['/kpi/report/export/excel'], type='http', auth='none')
    def export_kpi_excel(self, department_id=None, year=None, **kwargs):
        # Lấy dữ liệu từ model report.kpi
        records = request.env['report.kpi'].sudo().search([
            ('department_id', '=', int(department_id)),
            ('year', '=', int(year))
        ])

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('KPI Report')

        # Format cho tiêu đề
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'bg_color': '#D9E1F2'})
        center = workbook.add_format({'align': 'center'})
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
        })

        # Dòng tiêu đề cấp 1 (gộp ô)
        worksheet.merge_range(0, 0, 1, 0, "Tháng", header_format)
        worksheet.merge_range(0, 1, 0, 13, "Đơn vị đánh giá", header_format)
        worksheet.merge_range(0, 14, 0, 26, "Cấp thẩm quyền đánh giá", header_format)

        # Dòng tiêu đề cấp 2
        headers = [
            "Khối lượng \n CVTH", "Chất lượng CVTH", "Chấp hành nội quy", "Cải tiến, đề xuất, sáng kiến",
            "Σ Điểm đạt (trước khi + điểm tiến bộ)", "Ký hiệu (trước khi + điểm tiến bộ)",
            "Điểm Tiến bộ (+/-)", "Σ Điểm đạt (Đơn vị ĐG)", "Ký hiệu (sau khi + điểm tiến bộ)",
            "Xếp loại", "Kế hoạch", "Thực hiện",
            "Khối lượng CVTH", "Chất lượng CVTH", "Chấp hành nội quy", "Cải tiến, đề xuất, sáng kiến",
            "Σ Điểm đạt (trước khi + điểm tiến bộ)", "Ký hiệu (trước khi + điểm tiến bộ)",
            "Điểm Tiến bộ (+/-)", "Σ Điểm đạt (Đơn vị ĐG)", "Ký hiệu (sau khi + điểm tiến bộ)",
            "Xếp loại", "Kế hoạch", "Thực hiện"
        ]
        for i, h in enumerate(headers):
            worksheet.write(1, i + 1, h, header_format)

        # Ghi dữ liệu từ dòng 2 trở đi
        for row, rec in enumerate(records, start=2):
            worksheet.write(row, 0, rec.month, cell_format)

            worksheet.write(row, 1, rec.workload or 0.0, cell_format)
            worksheet.write(row, 2, rec.quality or 0.0, cell_format)
            worksheet.write(row, 3, rec.discipline or 0.0, cell_format)
            worksheet.write(row, 4, rec.improvement or 0.0, cell_format)
            worksheet.write(row, 5, rec.total_points_before or 0.0, cell_format)
            worksheet.write(row, 6, rec.symbol_before or '', cell_format)
            worksheet.write(row, 7, rec.progress_points or 0.0, cell_format)
            worksheet.write(row, 8, rec.total_points_after or 0.0, cell_format)
            worksheet.write(row, 9, rec.symbol_after or '', cell_format)
            worksheet.write(row, 10, rec.classification or '', cell_format)
            worksheet.write(row, 11, f"{rec.plan}%" if rec.plan else '', cell_format)
            worksheet.write(row, 12, f"{rec.criteria_achievement}%" if rec.criteria_achievement else '', cell_format)

            worksheet.write(row, 13, rec.tq_workload or 0.0, cell_format)
            worksheet.write(row, 14, rec.tq_quality or 0.0, cell_format)
            worksheet.write(row, 15, rec.tq_discipline or 0.0, cell_format)
            worksheet.write(row, 16, rec.tq_improvement or 0.0, cell_format)
            worksheet.write(row, 17, rec.tq_total_points_before or 0.0, cell_format)
            worksheet.write(row, 18, rec.tq_symbol_before or '', cell_format)
            worksheet.write(row, 19, rec.tq_progress_points or 0.0, cell_format)
            worksheet.write(row, 20, rec.tq_total_points_after or 0.0, cell_format)
            worksheet.write(row, 21, rec.tq_symbol_after or '', cell_format)
            worksheet.write(row, 22, rec.tq_classification or '', cell_format)
            worksheet.write(row, 23, f"{rec.tq_plan}%" if rec.tq_plan else '', cell_format)
            worksheet.write(row, 24, f"{rec.tq_criteria_achievement}%" if rec.tq_criteria_achievement else '', cell_format)

        workbook.close()
        output.seek(0)
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', 'attachment; filename="KPI_nam.xlsx"')
            ]
        )

    @http.route(['/kpi/report/month/export/excel'], type='http', auth='none')
    def export_kpi_month_excel(self, department_id=None, year=None, month=None, **kwargs):
        # Lấy dữ liệu từ model report.kpi
        records = request.env['sonha.kpi.result.month'].sudo().search([
            ('department_id', '=', int(department_id)),
            ('year', '=', int(year))
        ])

        records = records.filtered(lambda x: x.start_date.month == int(month))

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('KPI Tháng')
        header_format = workbook.add_format(
            {'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True,
             'bg_color': '#D9F1F1'})
        cell_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        text_format = workbook.add_format({'align': 'left', 'valign': 'top', 'border': 1, 'text_wrap': True})

        # Set column widths
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:D', 12)
        worksheet.set_column('E:E', 25)
        worksheet.set_column('F:F', 10)
        worksheet.set_column('G:G', 10)
        worksheet.set_column('H:H', 30)
        worksheet.set_column('I:J', 12)
        worksheet.set_column('K:K', 14)
        worksheet.set_column('L:M', 12)
        worksheet.set_column('N:N', 14)
        worksheet.set_column('O:O', 20)

        # Header rows
        worksheet.merge_range('A1:A2', 'NỘI DUNG CÔNG VIỆC\n(Đã giao ở mục tiêu/ KPIs cả năm)', header_format)
        worksheet.merge_range('B1:B2', 'NỘI DUNG CÔNG VIỆC CỤ THỂ', header_format)
        worksheet.merge_range('C1:D1', 'THỜI GIAN THỰC HIỆN', header_format)
        worksheet.write('C2', 'Bắt đầu', header_format)
        worksheet.write('D2', 'Hoàn thành', header_format)
        worksheet.merge_range('E1:E2', 'TIÊU CHÍ ĐÁNH GIÁ RÚT GỌN', header_format)
        worksheet.merge_range('F1:F2', 'Tỷ trọng', header_format)
        worksheet.merge_range('G1:G2', 'Điểm chuẩn', header_format)
        worksheet.merge_range('H1:H2', 'MÔ TẢ CHI TIẾT CÔNG VIỆC/ KIẾN NGHỊ ĐỀ XUẤT CỦA ĐƠN VỊ', header_format)
        worksheet.merge_range('I1:K1', 'Σ ĐIỂM ĐƠN VỊ ĐÁNH GIÁ', header_format)
        worksheet.write('I2', 'Kết quả hoàn thành', header_format)
        worksheet.write('J2', 'Điểm đạt', header_format)
        worksheet.write('K2', 'Điểm quy đổi theo tỷ trọng', header_format)
        worksheet.merge_range('L1:N1', 'Σ ĐIỂM CẤP THẨM QUYỀN ĐÁNH GIÁ', header_format)
        worksheet.write('L2', 'Kết quả hoàn thành', header_format)
        worksheet.write('M2', 'Điểm đạt', header_format)
        worksheet.write('N2', 'Điểm quy đổi theo tỷ trọng', header_format)
        worksheet.merge_range('O1:O2', 'NHẬN XÉT CỦA CẤP CÓ THẨM QUYỀN', header_format)

        row = 2
        for rec in records:
            # Merge các cột dùng chung cho cả 2 dòng
            worksheet.merge_range(row, 0, row + 1, 0, rec.name.name or '', text_format)
            worksheet.merge_range(row, 1, row + 1, 1, rec.content_detail or '', text_format)
            worksheet.merge_range(row, 2, row + 1, 2, rec.converted_start_date if rec.converted_start_date else '',
                                  cell_format)
            worksheet.merge_range(row, 3, row + 1, 3, rec.converted_end_date if rec.converted_end_date else '',
                                  cell_format)
            worksheet.merge_range(row, 5, row + 1, 5, f"{rec.ti_trong * 100}%", cell_format)
            worksheet.merge_range(row, 7, row + 1, 7, rec.dv_description or '', text_format)
            worksheet.merge_range(row, 14, row + 1, 14, rec.note or '', text_format)

            # Dòng 1: Khối lượng
            worksheet.write(row, 4, "Khối lượng công việc thực hiện", cell_format)
            worksheet.write(row, 6, rec.diem_chuan_amount_work or 0.0, cell_format)
            worksheet.write(row, 8, f"{rec.kq_hoan_thanh_amount_work * 100}%", cell_format)
            worksheet.write(row, 9, rec.diem_dat_dv_amount_work or 0.0, cell_format)
            worksheet.write(row, 10, rec.quy_doi_dv_amount_work or 0.0, cell_format)
            worksheet.write(row, 11, f"{rec.kq_hoan_thanh_tq_amount_work * 100}%", cell_format)
            worksheet.write(row, 12, rec.diem_dat_tq_amount_work or 0.0, cell_format)
            worksheet.write(row, 13, rec.quy_doi_tq_amount_work or 0.0, cell_format)

            # Dòng 2: Chất lượng
            worksheet.write(row + 1, 4, "Chất lượng công việc thực hiện", cell_format)
            worksheet.write(row + 1, 6, rec.diem_chuan_matter_work or 0.0, cell_format)
            worksheet.write(row + 1, 8, f"{rec.kq_hoan_thanh_matter_work * 100}%", cell_format)
            worksheet.write(row + 1, 9, rec.diem_dat_dv_matter_work or 0.0, cell_format)
            worksheet.write(row + 1, 10, rec.quy_doi_dv_matter_work or 0.0, cell_format)
            worksheet.write(row + 1, 11, f"{rec.kq_hoan_thanh_tq_matter_work * 100}%", cell_format)
            worksheet.write(row + 1, 12, rec.diem_dat_tq_matter_work or 0.0, cell_format)
            worksheet.write(row + 1, 13, rec.quy_doi_tq_matter_work or 0.0, cell_format)

            row += 2

        workbook.close()
        output.seek(0)
        filename = f'KPI_Report_{month}_{year}.xlsx'

        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename={filename}')
            ]
        )
