from odoo import http
from odoo.http import request
from datetime import datetime
from dateutil.relativedelta import relativedelta

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
        kpi_records = request.env['report.kpi.month'].sudo().search([('department_id', '=', department_id),
                                                                     ('year', '=', year)])
        if month:
            kpi_records = kpi_records.filtered(lambda x: x.start_date.month == month)
        if kpi_records:
            return request.render('sonha_kpi.report_kpi_month_rel_template', {
                'kpi_records': kpi_records
            })
        else:
            return "Chưa có dữ liệu đánh giá!"


    @http.route('/kpi/update_ajax', type='json', auth='none', methods=['POST'], csrf=False)
    def update_kpi_ajax(self, **kwargs):
        data = request.httprequest.get_json()
        for item in data["kpi_data"]:
            kpi_id = int(item["kpi_id"])
            field_name = item["field_name"]
            field_value = item["field_value"]
            if(str(field_value).isdigit()):
                convert_field = float(field_value)
                field_value = convert_field / 100
            kpi_record = request.env['sonha.kpi.month'].sudo().search([('id', '=', kpi_id)])
            if kpi_record and field_name:
                kpi_record.sudo().write({field_name: field_value})
            kpi_report = request.env['report.kpi.month'].sudo().search([('small_items_each_month.id', '=', kpi_id)])
            if kpi_report.status == 'waiting':
                kpi_report.sudo().write({'status': 'approved'})

    @http.route('/kpi/hr_approved', type='json', auth='none', csrf=False)
    def hr_approved(self):
        data = request.httprequest.get_json()
        for item in data["approve_data"]:
            department_id = int(item["department_id"])
            date = item["date"]
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
        if mail_to:
            template_id = request.env.ref('sonha_kpi.report_kpi_mail_template').sudo()
            if template_id:
                template_id.email_to = mail_to
                template_id.sudo().send_mail(kpi_records[0].id, force_send=True)

    @http.route('/kpi/cancel_kpi_approval', type='json', auth='none', csrf=False)
    def update_cancel_apptoval(self):
        data = request.httprequest.get_json()
        now = datetime.now().date()
        for item in data["cancel_data"]:
            kpi_id = int(item["kpi_id"])
            field_name = item["field_name"]
            kpi_record = request.env['sonha.kpi.month'].sudo().search([('id', '=', kpi_id)])
            if kpi_record and field_name:
                # if kpi_record.start_date <= now <= kpi_record.start_date + relativedelta(months=2, days=-1):
                kpi_record.sudo().write({field_name: 0})
                result_month_record = request.env['sonha.kpi.result.month'].sudo().search([('kpi_month', '=', kpi_id)])
                if result_month_record:
                    result_month_record.filter_data_dvtq(result_month_record)
                    kpi_report = request.env['report.kpi.month'].sudo().search([('small_items_each_month.id', '=', kpi_id)])
                    if kpi_report.status == 'approved' and kpi_report:
                        kpi_report.sudo().write({'status': 'waiting'})