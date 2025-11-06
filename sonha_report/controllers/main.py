from odoo import http
from odoo.http import request, Response
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import json

class HrEmployeeDashboardController(http.Controller):

    @http.route('/get_user_companies', type='http', auth='user', csrf=False)
    def get_user_companies(self):
        user = request.env.user
        companies = user.company_ids
        data = [
            {
                'id': c.id,
                'name': c.name,
                'is_default': c.id == user.company_id.id
            }
            for c in companies
        ]
        return Response(
            json.dumps(data, ensure_ascii=False),
            content_type='application/json;charset=utf-8'
        )

    @http.route('/get_employee_inout_data', type='http', auth='user', csrf=False)
    def get_employee_inout_data(self, **values):
        try:
            company_id = int(values.get('company_id', 0))
            year = int(values.get('year', 0))
            if not company_id or not year:
                return Response("[]", content_type='application/json')

            data = []

            query = "SELECT * FROM public.get_amount_employee_change(%s, %s)"
            request.env.cr.execute(query, (company_id, year))
            rows = request.env.cr.dictfetchall()
            for row in rows:
                data.append({
                        'month': f'Tháng {row["month"]}',
                        'onboard_count': row["onboard_count"],
                        'quit_count': row["quit_count"],
                    })
            return Response(
                json.dumps(data, ensure_ascii=False),
                content_type='application/json;charset=utf-8'
            )

        except Exception as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json;charset=utf-8',
                status=500
            )

    @http.route('/get_employee_as_contract_data', type='http', auth='user', csrf=False)
    def get_employee_department_data(self, **values):
        try:
            company_id = int(values.get('company_id', 0))
            year = int(values.get('year', 0))
            if not company_id:
                return Response("[]", content_type='application/json')

            data = []

            query = "SELECT * FROM public.get_employee_as_contract_data(%s, %s)"
            request.env.cr.execute(query, (company_id, year))
            rows = request.env.cr.dictfetchall()

            for row in rows:
                data.append({
                    'contract_type': row["contract_type"],
                    'count': row["amount"],
                })

            return Response(
                json.dumps(data, ensure_ascii=False),
                content_type='application/json;charset=utf-8'
            )

        except Exception as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json;charset=utf-8',
                status=500
            )

    @http.route('/get_amount_employee_data', type='http', auth='user', csrf=False)
    def get_amount_employee_data(self, **values):
        try:
            company_id = int(values.get('company_id', 0))
            year = int(values.get('year', 0))
            if not company_id or not year:
                return Response("[]", content_type='application/json')

            today = date.today()
            data = []

            query = "SELECT * FROM public.get_amount_employee_per_month(%s, %s)"
            request.env.cr.execute(query, (company_id, year))
            rows = request.env.cr.dictfetchall()
            for row in rows:
                if (year == today.year and row["month"] > today.month) or year > today.year:
                    data.append({
                        'month': f'Tháng {row["month"]}',
                        'count': 0,
                    })
                    continue
                data.append({
                        'month': f'Tháng {row["month"]}',
                        'count': row["employee_count"],
                    })

            return Response(
                json.dumps(data, ensure_ascii=False),
                content_type='application/json;charset=utf-8'
            )

        except Exception as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json;charset=utf-8',
                status=500
            )

