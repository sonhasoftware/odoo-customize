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

            for month in range(1, 13):
                start_date = datetime(year, month, 1)
                end_date = start_date + relativedelta(months=1)

                onboard_employees = request.env['hr.employee'].sudo().with_context(active_test=False).search([
                    ('company_id', '=', company_id),
                    ('onboard', '>=', start_date),
                    ('onboard', '<', end_date)
                ])
                quit_employees = request.env['hr.employee'].sudo().with_context(active_test=False).search([
                    ('company_id', '=', company_id),
                    ('date_quit', '>=', start_date),
                    ('date_quit', '<', end_date),
                    ('active', '=', False)
                ])

                data.append({
                    'month': f'Tháng {month}',
                    'onboard_count': len(onboard_employees),
                    'quit_count': len(quit_employees),
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

    @http.route('/get_employee_contract_data', type='http', auth='user', csrf=False)
    def get_employee_department_data(self, **values):
        try:
            company_id = int(values.get('company_id', 0))
            if not company_id:
                return Response("[]", content_type='application/json')

            employees = request.env['hr.employee'].sudo().search([
                ('company_id', '=', company_id)
            ])

            contract_counts = {}
            for emp in employees:
                if emp.contract_id:
                    contract_name = emp.contract_id.contract_type_id.name if emp.contract_id.contract_type_id else "Không xác định"
                else:
                    contract_name = "Không có hợp đồng"
                contract_counts[contract_name] = contract_counts.get(contract_name, 0) + 1

            data = [
                {'contract_type': name, 'count': count}
                for name, count in contract_counts.items()
            ]

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

            for month in range(1, 13):
                if (year == today.year and month > today.month) or year > today.year:
                    data.append({
                        'month': f'Tháng {month}',
                        'count': 0,
                    })
                    continue

                start_date = date(year, month, 1)
                end_date = start_date + relativedelta(months=1)

                employees = request.env['hr.employee'].sudo().with_context(active_test=False).search([
                    ('company_id', '=', company_id),
                    ('onboard', '<', end_date)
                ])

                # Lấy nhân viên vẫn còn làm trong tháng
                amount_employees = employees.filtered(
                    lambda x: not x.date_quit or x.date_quit >= start_date
                )

                data.append({
                    'month': f'Tháng {month}',
                    'count': len(amount_employees),
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

