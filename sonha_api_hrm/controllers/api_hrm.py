from odoo import http
from odoo.http import request, Response, route
import json
import logging
_logger = logging.getLogger(__name__)


class AuthAPI(http.Controller):

    @http.route('/api/login', type='http', auth='none', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        """
        API Login để xác thực người dùng và lưu session vào cookie
        """
        try:
            data = request.httprequest.get_json()  # Lấy dữ liệu JSON đúng cách
            login = data.get('login')
            password = data.get('password')

            if not login or not password:
                return Response(json.dumps({"success": False, "error": "Thiếu thông tin đăng nhập"}),
                                content_type="application/json", status=400)

            db = request.env.cr.dbname
            uid = request.session.authenticate(db, login, password)

            if uid:
                user = request.env['res.users'].sudo().browse(uid)
                employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)])

                # 🔥 Trả về response có Set-Cookie
                response = Response(json.dumps({
                    "success": True,
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "email": user.email,
                    },
                    "employee": {
                        "id": employee_id.id,
                        "name": employee_id.name,
                        "mail": employee_id.work_email,
                        "phone_number": employee_id.mobile_phone,
                        "employee_code": employee_id.employee_code,
                        "department": {
                            "id": employee_id.department_id.id,
                            "name": employee_id.department_id.name,
                        },
                        "job_position": {
                            "id": employee_id.job_id.id,
                            "name": employee_id.job_id.name,
                        },
                        "company_id": {
                            "id": employee_id.company_id.id,
                            "name": employee_id.company_id.name,
                        },

                    }
                }), content_type="application/json")

                return response
            else:
                return Response(json.dumps({"success": False, "error": "Đăng nhập thất bại"}),
                                content_type="application/json", status=401)

        except Exception as e:
            return Response(json.dumps({"success": False, "error": str(e)}), content_type="application/json",
                            status=500)

    @http.route('/api/get_word_slip_manager/<int:id_employee>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_pending_records(self, id_employee):
        try:
            list_records = request.env['form.word.slip'].sudo().search([
                '&',
                ('status', '=', 'draft'),
                '|',
                ('employee_confirm', '=', id_employee),
                ('employee_approval', '=', id_employee)
            ])
            data = []
            if list_records:
                for r in list_records:
                    word_slip_data = []
                    for slip in r.word_slip_id:
                        if slip.type.date_and_time == 'time':
                            word_slip_data.append({
                                "id": slip.id,
                                "from_date": str(slip.from_date) or '',
                                "to_date": str(slip.to_date) or '',
                                "time_to": slip.time_to or '',
                                "time_from": slip.time_from or '',
                                "reason": slip.reason or '',
                            })
                        else:
                            word_slip_data.append({
                                "id": slip.id,
                                "from_date": str(slip.from_date) or '',
                                "to_date": str(slip.to_date) or '',
                                "start_time": "Nửa ca đầu" if slip.start_time == 'first_half' else "Nửa ca sau",
                                "end_time": "Nửa ca đầu" if slip.end_time == 'first_half' else "Nửa ca sau",
                                "reason": slip.reason or '',
                            })
                    if r.regis_type == 'one':
                        data.append({
                            "id": r.id,
                            "code": r.code,
                            "status": "Chờ duyệt",
                            "regis_type": "Tạo cho tôi",
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": {
                                "id": r.employee_id.id,
                                "name": r.employee_id.name
                            }
                        })
                    else:
                        list_employee = []
                        for emp in r.employee_ids:
                            list_employee.append({
                                'id': emp.id,
                                'name': emp.name,
                            })
                        data.append({
                            "id": r.id,
                            "code": r.code,
                            "status": "Chờ duyệt",
                            "regis_type": "Tạo hộ",
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": list_employee
                        })

            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/config/word-slip/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_word_slip(self, company_id):
        try:
            list_records = request.env['config.word.slip'].sudo().search([('company_id', 'in', company_id)])
            data = []
            if list_records:
                for r in list_records:
                    company_id = []
                    for company in r.company_id:
                        if company:
                            company_id.append({
                                "id": company.id,
                                "name": company.name,
                            })
                    data.append({
                        "id": r.id,
                        "name": r.name,
                        "paid": r.paid,
                        "date_and_time": r.date_and_time,
                        "max_time": r.max_time,
                        "company_id": company_id,
                        "key": r.key or '',
                        })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/config-shift/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_shift(self, company_id):
        try:
            list_records = request.env['config.shift'].sudo().search([('company_id', 'in', company_id)])
            data = []
            if list_records:
                for r in list_records:
                    company_id = []
                    for company in r.company_id:
                        if company:
                            company_id.append({
                                "id": company.id,
                                "name": company.name,
                            })
                    data.append({
                        "id": r.id,
                        "code": r.code or '',
                        "name": r.name or '',
                        "earliest": r.earliest or '',
                        "overtime_before_shift": r.overtime_before_shift or '',
                        "start": str(r.start) or '',
                        "late_entry_allowed": r.late_entry_allowed or '',
                        "latest": r.latest or '',
                        "rest": r.rest or '',
                        "from_rest": str(r.from_rest) or '',
                        "minutes_rest": r.minutes_rest or '',
                        "to_rest": str(r.to_rest) or '',
                        "earliest_out": r.earliest_out or '',
                        "allow_early_exit": r.allow_early_exit or '',
                        "end_shift": str(r.end_shift) or '',
                        "overtime_after_shift": r.overtime_after_shift or '',
                        "latest_out": r.latest_out or '',
                        "night_shift": r.night_shift or '',
                        "night_shift_from": str(r.night_shift_from) or '',
                        "night_shift_to": str(r.night_shift_to) or '',
                        "effect_to": str(r.effect_to) or '',
                        "effect_from": str(r.effect_from) or '',
                        "using": r.using or '',
                        "note": r.note or '',
                        "contract": r.contract or '',
                        "company_id": company_id,
                        "is_office_hour": r.is_office_hour or '',
                        "night": r.night,
                        "c2k3": r.c2k3,
                        "c3k4": r.c3k4,
                        "half_shift": r.half_shift,
                    })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/config/public-leave', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_public_leave(self):
        try:
            list_records = request.env['resource.calendar.leaves'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "name": r.name or '',
                        "date_from": str(r.date_from) or '',
                        "date_to": str(r.date_to) or '',
                    })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/config/free-timekeeping', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_free_timekeeping(self):
        try:
            list_records = request.env['free.timekeeping'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "employee": {
                            "id": r.employee_id.id,
                            "name": r.employee_id.name,
                        },
                        "start_date": str(r.start_date) or '',
                        "end_date": str(r.end_date) or '',
                        "state": r.state,
                    })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/config/leave', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_leave(self):
        try:
            list_records = request.env['config.leave'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    employee_ids = []
                    for employee in r.employee_ids:
                        if employee:
                            employee_ids.append({
                                "id": employee.id,
                                "name": employee.name,
                            })
                    data.append({
                        "id": r.id,
                        "employee": employee_ids,
                        "start_date": {
                            "id": r.word_slip.id,
                            "name": r.word_slip.name,
                        },
                        "max_date": r.date,
                    })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/get_employee_company/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_employee_company(self, company_id):
        try:
            list_records = request.env['hr.employee'].sudo().search([
                ('company_id', '=', company_id)
            ])
            data = []
            if list_records:
                for emp in list_records:
                    data.append({
                        'id': emp.id,
                        'employee_code': emp.employee_code,
                        'name': emp.name,
                    })

            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/get_department_company/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_department_company(self, company_id):
        try:
            list_records = request.env['hr.department'].sudo().search([
                ('company_id', '=', company_id)
            ])
            data = []
            if list_records:
                for dep in list_records:
                    data.append({
                        'id': dep.id,
                        'name': dep.name,
                    })

            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

