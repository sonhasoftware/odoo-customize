from odoo import http
from odoo.http import request, Response, route
import json
import logging
_logger = logging.getLogger(__name__)


class AuthAPI(http.Controller):

    # api đăng nhập
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

    # api get ra đơn từ chờ duyệt
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

    # api get ra danh mục đơn từ
    @http.route('/api/config/word-slip/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_word_slip(self, company_id):
        try:
            list_records = request.env['config.word.slip'].sudo().search([('company_id', 'in', company_id)])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "name": r.name,
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

    # api get ra danh mục ca
    @http.route('/api/config-shift/<int:company_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_config_shift(self, company_id):
        try:
            list_records = request.env['config.shift'].sudo().search([('company_id', 'in', company_id)])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "code": r.code or '',
                        "name": r.name or '',
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

    # api get ra cấu hình nghỉ lễ
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

    # api get danh sách miễn chấm công
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

    # api get ra cấu hình số đơn làm trong 1 tháng
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

    # api get nhân viên theo công ty
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

    # api get phòng ban theo công ty
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

