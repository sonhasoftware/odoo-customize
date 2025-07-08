from odoo import http
from odoo.http import request, Response, route
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta
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
            device_id = data.get('device_id')

            if not login or not password:
                return Response(json.dumps({"success": False, "error": "Thiếu thông tin đăng nhập"}),
                                content_type="application/json", status=400)
            user_id = request.env['res.users'].sudo().search([('login', '=', login)])
            if user_id and user_id.device_number != 0:
                device = request.env['res.users'].sudo().search([('device_id', '=', device_id)], limit=1)
                if device and device.login != login:
                    return Response(json.dumps({"success": False,
                                                "error": "Thiết bị này đã được đăng ký cho tài khoản " + device.login}),
                                    content_type="application/json", status=400)

            db = request.env.cr.dbname
            uid = request.session.authenticate(db, login, password)

            if uid:
                user = request.env['res.users'].sudo().browse(uid)
                employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)])
                total_leave = employee_id.old_leave_balance + employee_id.new_leave_balance

                # 🔥 Trả về response có Set-Cookie
                response = Response(json.dumps({
                    "success": True,
                    "user": {
                        "id": user.id,
                        "name": user.name,
                        "email": user.email,
                        "device_id": user.device_id or "",
                        "token": user.token,
                        "option_check": user.option_check,
                        "device_number": user.device_number,
                    },
                    "employee": {
                        "id": employee_id.id,
                        "name": employee_id.name,
                        "mail": employee_id.work_email,
                        "phone_number": employee_id.sonha_number_phone,
                        "leave_old": employee_id.old_leave_balance,
                        "leave_new": total_leave,
                        "employee_code": employee_id.employee_code,
                        "device_id_num": employee_id.device_id_num,
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

    @http.route('/api/attendance_wifi', type='http', auth='none', methods=['POST'], csrf=False)
    def api_attendance_wifi(self, **kwargs):
        try:
            now = datetime.now()
            data = request.httprequest.get_json()  # Lấy dữ liệu JSON đúng cách
            device_id_num = data.get('device_id_num')
            if not device_id_num:
                return Response(json.dumps({"success": False,
                                            "error": "Không tồn tại mã chấm công"}),
                                content_type="application/json", status=400)
            employee_id = request.env['hr.employee'].sudo().search([('device_id_num', '=', device_id_num)])
            if not employee_id:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy thông tin nhân viên"}),
                                content_type="application/json", status=400)
            now = datetime.now()
            vals = {
                'employee_id': employee_id.id,
                'attendance_time': now,
                'attendance_type': "Wifi"
            }
            request.env['master.data.attendance'].sudo().create(vals)
            return Response(
                json.dumps({"success": True}),
                status=200, content_type="application/json"
            )
        except Exception as e:
            return Response(json.dumps({"success": False, "error": str(e)}), content_type="application/json",
                            status=500)

    # api get ra đơn từ chờ duyệt
    @http.route('/api/get_word_slip_manager/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
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
                    employee_create = []
                    if r.create_uid:
                        create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                        employee_create.append({
                            "id": create_employee.id,
                            "name": create_employee.name,
                        })
                    date_sent = r.create_date + relativedelta(hours=7)
                    word_slip_data = []
                    for slip in r.word_slip_id:
                        if slip.type.date_and_time == 'time':
                            hours_start = int(slip.time_to)
                            minutes_start = int(round((slip.time_to - hours_start) * 60))
                            time_start = f"{hours_start:02d}:{minutes_start:02d}"

                            hours_end = int(slip.time_from)
                            minutes_end = int(round((slip.time_from - hours_end) * 60))
                            time_end = f"{hours_end:02d}:{minutes_end:02d}"
                            word_slip_data.append({
                                "id": slip.id,
                                "from_date": str(slip.from_date) or '',
                                "to_date": str(slip.to_date) or '',
                                "time_to": time_start or '',
                                "time_from": time_end or '',
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
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": {
                                "id": r.employee_id.id,
                                "name": r.employee_id.name
                            },
                            "employee_create": employee_create
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
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": list_employee,
                            "employee_create": employee_create
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
                        "type": r.date_and_time
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

    @http.route('/api/get_word_slip_user/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_word_slip_user(self, id_employee):
        try:
            list_records = request.env['form.word.slip'].sudo().search([
                '|',
                ('employee_id', '=', id_employee),
                ('employee_ids', 'in', id_employee)
            ])
            data = []
            if list_records:
                for r in list_records:
                    employee_create = []
                    if r.create_uid:
                        create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                        employee_create.append({
                            "id": create_employee.id,
                            "name": create_employee.name,
                        })
                    date_sent = r.create_date + relativedelta(hours=7)
                    if r.status == 'sent':
                        state = "Nháp"
                    elif r.status == 'draft':
                        state = "Chờ duyệt"
                    elif r.status == 'done':
                        state = "Đã duyệt"
                    else:
                        state = "Hủy"
                    word_slip_data = []
                    for slip in r.word_slip_id:
                        if slip.type.date_and_time == 'time':
                            hours_start = int(slip.time_to)
                            minutes_start = int(round((slip.time_to - hours_start) * 60))
                            time_start = f"{hours_start:02d}:{minutes_start:02d}"

                            hours_end = int(slip.time_from)
                            minutes_end = int(round((slip.time_from - hours_end) * 60))
                            time_end = f"{hours_end:02d}:{minutes_end:02d}"
                            word_slip_data.append({
                                "id": slip.id,
                                "from_date": str(slip.from_date) or '',
                                "to_date": str(slip.to_date) or '',
                                "time_to": time_start or '',
                                "time_from": time_end or '',
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
                            "status": state,
                            "regis_type": "Tạo cho tôi",
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": {
                                "id": r.employee_id.id,
                                "name": r.employee_id.name
                            },
                            "employee_create": employee_create
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
                            "status": state,
                            "regis_type": "Tạo hộ",
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": list_employee,
                            "employee_create": employee_create
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

    @http.route('/api/get_word_slip_id/<int:id>/<int:employee_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_word_slip_id(self, id, employee_id):
        try:
            r = request.env['form.word.slip'].sudo().search([
                ('id', '=', id)
            ])
            employee_create = []
            if r.create_uid:
                create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                employee_create.append({
                    "id": create_employee.id,
                    "name": create_employee.name,
                })
            user_id = request.env['hr.employee'].sudo().search([('id', '=', employee_id)]).user_id
            data = []
            list_employee = [r.employee_id.id] or r.employee_ids.ids
            check_button_sent = False
            check_button_done = False
            if ((employee_id in list_employee) or (r.create_uid.id and user_id.id == r.create_uid.id)) and r.status == 'sent':
                check_button_sent = True
            if (r.employee_confirm and employee_id == r.employee_confirm.id and r.status == 'draft') or (r.employee_approval and employee_id == r.employee_approval.id and r.status == 'draft'):
                check_button_done = True
            if r:
                date_sent = r.create_date + relativedelta(hours=7)
                if r.status == 'sent':
                    state = "Nháp"
                elif r.status == 'draft':
                    state = "Chờ duyệt"
                elif r.status == 'done':
                    state = "Đã duyệt"
                else:
                    state = "Hủy"
                word_slip_data = []
                for slip in r.word_slip_id:
                    if slip.type.date_and_time == 'time':
                        hours_start = int(slip.time_to)
                        minutes_start = int(round((slip.time_to - hours_start) * 60))
                        time_start = f"{hours_start:02d}:{minutes_start:02d}"

                        hours_end = int(slip.time_from)
                        minutes_end = int(round((slip.time_from - hours_end) * 60))
                        time_end = f"{hours_end:02d}:{minutes_end:02d}"

                        word_slip_data.append({
                            "id": slip.id,
                            "from_date": str(slip.from_date) or '',
                            "to_date": str(slip.to_date) or '',
                            "time_to": time_start or '',
                            "time_from": time_end or '',
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
                        "department_id": {
                            "id": r.department.id,
                            "name": r.department.name
                        },
                        "code": r.code,
                        "status": state,
                        "regis_type": "Tạo cho tôi",
                        "date_sent": str(date_sent),
                        "type": {
                            "id": r.type.id,
                            "name": r.type.name
                        },
                        "date": word_slip_data,
                        "employee_id": {
                            "id": r.employee_id.id,
                            "name": r.employee_id.name
                        },
                        "button_sent": check_button_sent,
                        "button_done": check_button_done,
                        "employee_create": employee_create
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
                        "department_id": {
                            "id": r.department.id,
                            "name": r.department.name
                        },
                        "code": r.code,
                        "status": state,
                        "regis_type": "Tạo hộ",
                        "date_sent": str(date_sent),
                        "type": {
                            "id": r.type.id,
                            "name": r.type.name
                        },
                        "date": word_slip_data,
                        "employee_id": list_employee,
                        "button_sent": check_button_sent,
                        "button_done": check_button_done,
                        "employee_create": employee_create
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

    # api danh sách đổi ca
    @http.route('/api/register_list_shift', type='http', auth='none', methods=['GET'], csrf=False)
    def get_register_list_shift(self):
        try:
            list_records = request.env['register.shift'].sudo().search([])
            data = []
            if list_records:
                for record in list_records:
                    data_date = []
                    if record.register_rel:
                        for detail in record.register_rel:
                            data_date.append({
                                'date': str(detail.date),
                                'shift': {
                                    'id': detail.shift.id,
                                    'name': detail.shift.name,
                                }
                            })
                    data.append({
                        'id': record.id,
                        'shift': data_date,
                        'department': {
                            'id': record.department_id.id,
                            'name': record.department_id.name
                        },
                        'employee': {
                            'id': record.employee_id.id,
                            'name': record.employee_id.name
                        },
                        'reason': record.description,
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

    # api đơn đổi ca chi tiết
    @http.route('/api/register_shift/<int:id_record>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_register_shift(self, id_record):
        try:
            list_records = request.env['register.shift'].sudo().search([
                ('id', '=', id_record)
            ])
            data = []
            if list_records:
                for record in list_records:
                    data_date = []
                    if record.register_rel:
                        for detail in record.register_rel:
                            data_date.append({
                                'date': str(detail.date),
                                'shift': {
                                    'id': detail.shift.id,
                                    'name': detail.shift.name,
                                }
                            })
                    data.append({
                        'id': record.id,
                        'shift': data_date,
                        'department': {
                            'id': record.department_id.id,
                            'name': record.department_id.name
                        },
                        'employee': {
                            'id': record.employee_id.id,
                            'name': record.employee_id.name
                        },
                        'reason': record.description,
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

    # api chi tiết đăng ký ca làm việc
    @http.route('/api/register_work/<int:id_record>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_register_work(self, id_record):
        try:
            list_records = request.env['register.work'].sudo().search([
                ('id', '=', id_record)
            ])
            data = []
            if list_records:
                for record in list_records:
                    data_employee = []
                    if record.employee_id:
                        for employee_id in record.employee_id:
                            data_employee.append({
                                'id': employee_id.id,
                                'name': employee_id.name,
                            })
                    data.append({
                        'id': record.id,
                        'department': {
                            'id': record.department_id.id,
                            'name': record.department_id.name
                        },
                        'start_time': str(record.start_date),
                        'end_time': str(record.end_date),
                        'shift': {
                            'id': record.shift.id,
                            'name': record.shift.name
                        },
                        'employee_id': data_employee,
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

    # api danh sách đăng ký ca làm việc
    @http.route('/api/register_work_list', type='http', auth='none', methods=['GET'], csrf=False)
    def get_register_work_list(self):
        try:
            list_records = request.env['register.work'].sudo().search([
            ])
            data = []
            if list_records:
                for record in list_records:
                    data_employee = []
                    if record.employee_id:
                        for employee_id in record.employee_id:
                            data_employee.append({
                                'id': employee_id.id,
                                'name': employee_id.name,
                            })
                    data.append({
                        'id': record.id,
                        'department': {
                            'id': record.department_id.id,
                            'name': record.department_id.name
                        },
                        'start_time': str(record.start_date),
                        'end_time': str(record.end_date),
                        'shift': {
                            'id': record.shift.id,
                            'name': record.shift.name
                        },
                        'employee_id': data_employee,
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

    @http.route('/api/get_synthetic_work/<int:employee_id>/<int:month>/<int:year>', type='http', auth='none', methods=['GET'],csrf=False)
    def get_synthetic_work(self, employee_id, month, year):
        try:
            data = []
            list_record = request.env['synthetic.work'].sudo().search([
                ('employee_id', '=', employee_id),
                ('month', '=', month),
                ('year', '=', year)
            ])
            if list_record:
                for record in list_record:
                    data.append({
                        'employee_id': record.employee_id.name,
                        'employee_code': record.employee_code,
                        'department_id': record.department_id.name,
                        'total_work': record.total_work,
                        'date_work': record.date_work,
                        'ot_one_hundred': record.ot_one_hundred,
                        'paid_leave': record.paid_leave,
                        'number_minutes_late': record.number_minutes_late,
                        'number_minutes_early': record.number_minutes_early,
                        'shift_two_crew_three': record.shift_two_crew_three,
                        'shift_three_crew_four': record.shift_three_crew_four,
                        'on_leave': record.on_leave,
                        'compensatory_leave': record.compensatory_leave,
                        'vacation': record.vacation,
                        'public_leave': record.public_leave,
                        'month': record.month,
                        'year': record.year,

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

    @http.route('/api/create/word_slip/<int:employee_id>', type='http', auth='none', methods=['POST'], csrf=False)
    def api_create_word_slip(self, employee_id):
        try:
            with request.env.cr.savepoint():
                data = request.httprequest.get_json()

                # Lấy dữ liệu từ request
                department_id = data.get('department_id')
                regis_type = data.get('regis_type')
                type_slip = data.get('type_slip')
                employee = data.get('employee')
                employees = data.get('employees', [])
                date_data = data.get('date', [])
                if not employee_id:
                    raise ValueError("Không có dữ liệu người đăng nhập!")
                user_id = request.env['hr.employee'].sudo().search([('id', '=', employee_id)]).user_id

                # Gộp danh sách employee để tìm công ty
                list_emp = [employee] if employee else employees
                if not list_emp:
                    raise ValueError("Dữ liệu nhân viên không được để trống!")
                if not department_id:
                    raise ValueError("Dữ liệu phòng ban không được để trống!")
                if not regis_type:
                    raise ValueError("Loại đăng ký không được để trống!")
                if not type_slip:
                    raise ValueError("Loại đơn không được để trống!")

                employee_record = request.env['hr.employee'].sudo().search([('id', 'in', list_emp)], limit=1)
                if not employee_record:
                    raise ValueError("Không tìm thấy nhân viên phù hợp!")
                department_record = request.env['hr.department'].sudo().search([('id', '=', department_id)], limit=1)
                if not department_record:
                    raise ValueError("Không tìm thấy phòng ban phù hợp!")

                company = employee_record.company_id

                # Xử lý dữ liệu dòng ngày nghỉ
                date_lines = []
                for d in date_data:
                    float_from = 0
                    float_to = 0
                    time_from = d.get("time_from"),
                    time_from = time_from[0]
                    time_to = d.get("time_to"),
                    time_to = time_to[0]
                    if time_from not in (None, '', False):
                        time_obj = datetime.strptime(time_from, "%H:%M")
                        float_from = time_obj.hour + time_obj.minute / 60.0
                    if time_to not in (None, '', False):
                        time_obj = datetime.strptime(time_to, "%H:%M")
                        float_to = time_obj.hour + time_obj.minute / 60.0
                    date_lines.append((0, 0, {
                        "from_date": str(d.get("from_date")),
                        "to_date": str(d.get("to_date")),
                        "start_time": d.get("start_time"),
                        "end_time": d.get("end_time"),
                        "time_from": float_from,
                        "time_to": float_to,
                        "reason": d.get("reason"),
                    }))

                # Chuẩn bị dữ liệu tạo bản ghi
                vals = {
                    'department': department_id,
                    'regis_type': regis_type,
                    'type': type_slip,
                    'word_slip_id': date_lines,
                    'employee_id': employee,
                    'status': 'sent',
                    'status_lv1': 'sent',
                    'status_lv2': 'sent',
                    'company_id': company.id,
                    'employee_ids': [(6, 0, employees)],
                }

                # Tạo record
                record = request.env['form.word.slip'].with_user(user_id).sudo().create(vals)

                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id
                }), content_type="application/json", status=200)

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/change/status/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_change_status(self, id):
        try:
            record = request.env['form.word.slip'].sudo().search([('id', '=', id)])
            employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', record.create_uid.id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            else:
                vals = {}
                if not record.check_level:
                    if record.status == 'sent':
                        record.status = 'draft'
                        record.status_lv1 = 'draft'
                        vals = {
                            'employee_id': record.employee_approval.id,
                            'user_id': record.employee_approval.user_id.id,
                            'token': record.employee_approval.user_id.token or "",
                            'create_user_id':  {
                                'id': record.create_uid.id,
                                'name': record.create_uid.name,
                            },
                            'create_employee_id': employee_id.id if employee_id else None,
                            'code': record.code or "",
                            'type': {
                                'id': record.type.id,
                                'name': record.type.name,
                            }
                        }
                    elif record.status == 'draft':
                        record.status = 'done'
                        record.status_lv1 = 'done'
                        vals = {
                            'token': employee_id.user_id.token or "",
                            'create_user_id':  {
                                'id': record.create_uid.id,
                                'name': record.create_uid.name,
                            },
                            'create_employee_id': employee_id.id if employee_id else None,
                            'code': record.code or "",
                            'type': {
                                'id': record.type.id,
                                'name': record.type.name,
                            }
                        }
                else:
                    if record.status_lv2 == 'sent':
                        record.status = 'draft'
                        record.status_lv2 = 'draft'
                        vals = {
                            'employee_id': record.employee_confirm.id,
                            'user_id': record.employee_confirm.user_id.id,
                            'token': record.employee_confirm.user_id.token or "",
                            'create_user_id':  {
                                'id': record.create_uid.id,
                                'name': record.create_uid.name,
                            },
                            'create_employee_id': employee_id.id if employee_id else None,
                            'code': record.code or "",
                            'type': {
                                'id': record.type.id,
                                'name': record.type.name,
                            }
                        }
                    elif record.status_lv2 == 'draft':
                        record.status = 'draft'
                        record.status_lv1 = 'confirm'
                        vals = {
                            'employee_id': record.employee_approval.id,
                            'user_id': record.employee_approval.user_id.id,
                            'token': record.employee_approval.user_id.token or "",
                            'create_user_id':  {
                                'id': record.create_uid.id,
                                'name': record.create_uid.name,
                            },
                            'create_employee_id': employee_id.id if employee_id else None,
                            'code': record.code or "",
                            'type': {
                                'id': record.type.id,
                                'name': record.type.name,
                            }
                        }
                    elif record.status_lv2 == 'confirm':
                        record.status = 'done'
                        record.status_lv1 = 'done'
                        vals = {
                            'token': employee_id.user_id.token or "",
                            'create_user_id':  {
                                'id': record.create_uid.id,
                                'name': record.create_uid.name,
                            },
                            'create_employee_id': employee_id.id if employee_id else None,
                            'code': record.code or "",
                            'type': {
                                'id': record.type.id,
                                'name': record.type.name,
                            }
                        }

                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id,
                    "data": vals,
                    "msg": "Bấm nút thành công",
                }), content_type="application/json", status=200)

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/get_word_slip_user_waiting/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_word_slip_user_waiting(self, id_employee):
        try:
            list_records = request.env['form.word.slip'].sudo().search([
                '&',
                ('status', '=', 'draft'),
                '|',
                ('employee_id', '=', id_employee),
                ('employee_ids', 'in', id_employee)
            ])
            data = []
            if list_records:
                for r in list_records:
                    employee_create = []
                    if r.create_uid:
                        create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                        employee_create.append({
                            "id": create_employee.id,
                            "name": create_employee.name,
                        })
                    date_sent = r.create_date + relativedelta(hours=7)
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
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": {
                                "id": r.employee_id.id,
                                "name": r.employee_id.name
                            },
                            "employee_create": employee_create
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
                            "date_sent": str(date_sent),
                            "type": {
                                "id": r.type.id,
                                "name": r.type.name
                            },
                            "date": word_slip_data,
                            "employee_id": list_employee,
                            "employee_create": employee_create
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

    @http.route('/api/status/cancel/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_status_cancel(self, id):
        try:
            record = request.env['form.word.slip'].sudo().search([('id', '=', id)])
            employee_id = request.env['hr.employee'].sudo().search([('user_id', '=', record.create_uid.id)])
            vals = {}
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            else:
                record.status = 'cancel'
                record.status_lv1 = 'cancel'
                record.status_lv2 = 'cancel'
                vals = {
                    'token': employee_id.user_id.token or "",
                    'create_user_id': {
                        'id': record.create_uid.id,
                        'name': record.create_uid.name,
                    },
                    'create_employee_id': employee_id.id if employee_id else None,
                    'code': record.code or "",
                    'type': {
                        'id': record.type.id,
                        'name': record.type.name,
                    }
                }

                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id,
                    "data": vals,
                    "msg": "Bấm nút thành công",
                }), content_type="application/json", status=200)

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/back/status/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_back_status(self, id):
        try:
            record = request.env['form.word.slip'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            else:
                record.status = 'sent'
                record.status_lv1 = 'sent'
                record.status_lv2 = 'sent'

                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id,
                    "msg": "Bấm nút thành công",
                }), content_type="application/json", status=200)

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/work/detail/<int:employee_id>/<date>', type='http', auth='none', methods=['GET'], csrf=False)
    def api_work_detail(self, employee_id, date):
        try:
            if not employee_id:
                raise ValueError("Không tìm thấy dữ liệu nhân viên")
            if not date:
                raise ValueError("Không tìm thấy dữ liệu ngày")
            date_obj = datetime.strptime(date, "%d-%m-%Y").date()
            # date_obj = datetime.strptime(date, "%d-%m-%Y")
            # new_date_str = date_obj.strftime("%d/%m/%Y")
            record = request.env['employee.attendance'].sudo().search([
                ('employee_id', '=', employee_id),
                ('date', '=', date_obj),
            ])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            else:
                check_in_plus_7 = record.check_in + timedelta(hours=7) if record.check_in else None
                check_out_plus_7 = record.check_out + timedelta(hours=7) if record.check_out else None
                data = {
                    "employee_id": {
                        "id": record.employee_id.id,
                        "name": record.employee_id.name,
                    },
                    "department_id": {
                        "id": record.department_id.id,
                        "name": record.department_id.name,
                    },
                    "date": str(record.date),
                    "check_in": check_in_plus_7.strftime("%H:%M:%S") if check_in_plus_7 else None,
                    "check_out": check_out_plus_7.strftime("%H:%M:%S") if check_out_plus_7 else None,
                    "shift": {
                        "id": record.shift.id,
                        "name": record.shift.name,
                    },
                    "work_day": record.work_day,
                    "note": record.note if record.note else "",
                    "minutes_late": record.minutes_late,
                    "minutes_early": record.minutes_early,
                    "over_time": record.over_time,
                    "leave": record.leave,
                    "compensatory": record.compensatory,
                    "public_leave": record.public_leave,
                    "c2k3": record.c2k3,
                    "c3k4": record.c3k4,
                    "shift_toxic": record.shift_toxic,
                    "color": record.color if record.color else "",
                }

                # Trả về kết quả
                return Response(
                    json.dumps({"success": True, "data": data}),
                    status=200, content_type="application/json"
                )

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/delete_record/<int:record_id>/<int:employee_id>', type='http', auth='none', methods=['DELETE'], csrf=False)
    def api_delete_record(self, record_id, employee_id):
        try:
            record = request.env['form.word.slip'].sudo().search([('id', '=', record_id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")

            if not employee_id:
                raise ValueError("Không có dữ liệu user")

            create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', record.create_uid.id)])

            list_emp = [record.employee_id.id] or record.employee_ids.ids
            if (employee_id in list_emp or employee_id == create_employee.id) and record.status == 'sent':
                record.sudo().unlink()
            else:
                raise ValueError("Chỉ được xóa bản ghi ở trạng thái nháp")

            # Trả về kết quả
            return Response(json.dumps({
                "success": True,
                "msg": "Xóa thành công bản ghi",
            }), content_type="application/json", status=200)

        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/get/employee_department/<int:department_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_employee_department(self, department_id):
        try:
            if not department_id:
                raise ValueError("Không tìm thấy dữ liệu phòng ban")
            list_emp = request.env['hr.employee'].sudo().search([('department_id', '=', department_id)])
            if not list_emp:
                raise ValueError("Không tìm thấy dữ liệu nhân viên trong phòng ban")
            data = []
            for r in list_emp:
                data.append({
                    'id': r.id,
                    'employee_code': r.employee_code,
                    'name': r.name,
                })
                # Trả về kết quả
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/device/<int:user_id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_fill_device(self, user_id):
        try:
            data = request.httprequest.get_json()  # Lấy dữ liệu JSON đúng cách
            device_id = data.get('device_id')
            device_number = data.get('device_number')

            if not user_id:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu nhân viên!"}),
                                content_type="application/json",
                                status=400)
            if not device_id:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu thiết bị!"}),
                                content_type="application/json",
                                status=400)

            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu nhân viên!"}),
                                content_type="application/json",
                                status=400)
            user.write({
                'device_id': device_id,
                'device_number': device_number,
            })
            return Response(json.dumps({
                "success": True,
                "msg": "Cập nhật thiết bị thành công",
            }), content_type="application/json", status=200)

        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/token/<int:user_id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_fill_token(self, user_id):
        try:
            data = request.httprequest.get_json()  # Lấy dữ liệu JSON đúng cách
            token = data.get('token')

            if not user_id:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu nhân viên!"}),
                                content_type="application/json",
                                status=400)
            if not token:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu token!"}),
                                content_type="application/json",
                                status=400)

            user = request.env['res.users'].sudo().browse(user_id)
            if not user:
                return Response(json.dumps({"success": False,
                                            "error": "Không tìm thấy dữ liệu nhân viên!"}),
                                content_type="application/json",
                                status=400)
            user.write({
                'token': token,
            })
            return Response(json.dumps({
                "success": True,
                "msg": "Cập nhật token thành công",
            }), content_type="application/json", status=200)

        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/total_work_detail/<int:employee_id>/<int:month>/<int:year>', type='http', auth='none', methods=['GET'], csrf=False)
    def total_work_detail(self, employee_id, month, year):
        try:
            if not employee_id:
                raise ValueError("Không tìm thấy dữ liệu nhân viên")
            records = request.env['employee.attendance'].sudo().search([
                ('employee_id', '=', employee_id),
                ('month', '=', month),
                ('year', '=', year),
            ])
            if not records:
                raise ValueError("Không tìm thấy bản ghi")
            data = []
            list_detail = []
            for record in records:
                check_in_plus_7 = record.check_in + timedelta(hours=7) if record.check_in else None
                check_out_plus_7 = record.check_out + timedelta(hours=7) if record.check_out else None
                list_detail.append({
                    "date": str(record.date),
                    "check_in": check_in_plus_7.strftime("%H:%M:%S") if check_in_plus_7 else None,
                    "check_out": check_out_plus_7.strftime("%H:%M:%S") if check_out_plus_7 else None,
                    "shift": {
                        "id": record.shift.id,
                        "name": record.shift.name,
                    },
                    "work_day": record.work_day,
                    "note": record.note if record.note else "",
                    "minutes_late": record.minutes_late,
                    "minutes_early": record.minutes_early,
                    "over_time": record.over_time,
                    "leave": record.leave,
                    "compensatory": record.compensatory,
                    "public_leave": record.public_leave,
                    "c2k3": record.c2k3,
                    "c3k4": record.c3k4,
                    "shift_toxic": record.shift_toxic,
                    "color": record.color if record.color else "",
                    "work_calendar": record.work_calendar,
                })
            data.append({
                "employee_id": {
                    "id": records[1].employee_id.id,
                    "name": records[1].employee_id.name,
                },
                "department_id": {
                    "id": records[1].department_id.id,
                    "name": records[1].department_id.name,
                },
                "list_data": list_detail
            })

            # Trả về kết quả
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )

        except Exception as e:
            # Log lỗi cho admin (nếu cần)
            request.env.cr.rollback()  # Dự phòng rollback toàn bộ transaction
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/remote/timekeeping', type='http', auth='none', methods=['GET'], csrf=False)
    def get_remote_timekeeping(self):
        try:
            list_records = request.env['remote.timekeeping'].sudo().search([])
            if not list_records:
                raise ValueError("Không tìm thấy dữ liệu!")
            data = []
            for r in list_records:
                data.append({
                    "id": r.id,
                    "name": r.name,
                    "bssid": r.bssid,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "radiusInMeters": r.radius,
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

    @http.route('/api/log_notifi', type='http', auth='none', methods=['POST'], csrf=False)
    def api_log_notifi(self, **kwargs):
        """
        API Login để xác thực người dùng và lưu session vào cookie
        """
        try:
            data = request.httprequest.get_json()  # Lấy dữ liệu JSON đúng cách
            token = data.get('token')
            title = data.get('title')
            body = data.get('body')
            data_field = data.get('data')
            type = data.get('type')
            taget_screen = data.get('taget_screen')
            message_id = data.get('message_id')
            badge = data.get('badge')
            datetime_str = data.get('datetime')
            userid = data.get('userid')
            employeeid = data.get('employeeid')
            id_application = data.get('id_application')

            required_fields = [
                'token',
                'title',
                'body',
                'data_field',
                'type',
                'taget_screen',
                'message_id',
                'badge',
                'datetime_str',
                'userid',
                'employeeid',
                'id_application'
            ]

            # Kiểm tra và trả lỗi nếu thiếu
            for field_name in required_fields:
                if not locals().get(field_name):
                    return Response(
                        json.dumps({"success": False, "error": f"Thiếu thông tin: {field_name}"}),
                        content_type="application/json", status=400
                    )

            datetime_obj = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")

            vals = {
                'token': token,
                'title': title,
                'body': body,
                'data': data_field,
                'type': type,
                'taget_screen': taget_screen,
                'message_id': message_id,
                'badge': badge,
                'datetime': datetime_obj,
                'userid': userid,
                'employeeid': employeeid,
                'id_application': id_application,
            }
            request.env['log.notifi'].sudo().create(vals)

            return Response(json.dumps({
                "success": True,
                "msg": "Tạo dữ liệu thành công",
            }), content_type="application/json", status=200)

        except Exception as e:
            return Response(json.dumps({"success": False, "error": str(e)}), content_type="application/json",
                            status=500)

    @http.route('/api/write/log_notifi/<int:record_id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_write_log_notifi(self, record_id, **kwargs):
        """
        API Login để xác thực người dùng và lưu session vào cookie
        """
        try:
            if not record_id:
                raise ValueError("Không tìm thấy bản ghi")
            data = request.httprequest.get_json()
            is_read = data.get('is_read')
            if not is_read:
                raise ValueError("Không tìm is_read")
            record = request.env['log.notifi'].sudo().browse(record_id)
            if is_read == 1:
                record.is_read = True
            return Response(json.dumps({
                "success": True,
                "msg": "Cập nhật dữ liệu thành công!",
            }), content_type="application/json", status=200)

        except Exception as e:
            return Response(json.dumps({"success": False, "error": str(e)}), content_type="application/json",
                            status=500)

    @http.route('/api/get/log_notifi/<userid>/<from_date>/<to_date>', type='http', auth='none', methods=['GET'], csrf=False)
    def api_get_log_notifi(self, userid, from_date, to_date):
        try:
            if not userid:
                raise ValueError("Không tìm thấy dữ liệu userid")
            if not from_date:
                raise ValueError("Không tìm thấy dữ liệu from_date")
            if not to_date:
                raise ValueError("Không tìm thấy dữ liệu to_date")
            date_start = datetime.strptime(from_date, "%Y-%m-%d %H:%M:%S")
            date_end = datetime.strptime(to_date, "%Y-%m-%d %H:%M:%S")
            logs = request.env['log.notifi'].sudo().search([
                ('userid', '=', userid),
                ('datetime', '>=', date_start),
                ('datetime', '<=', date_end)
            ])
            data = []
            if logs:
                for log in logs:
                    data.append({
                        'id': log.id,
                        'token': log.token or "",
                        'title': log.title or "",
                        'body': log.body or "",
                        'data': log.data or "",
                        'type': log.type or "",
                        'taget_screen': log.taget_screen or "",
                        'message_id': log.message_id or "",
                        'badge': log.badge or "",
                        'datetime': str(log.datetime) if log.datetime else None,
                        'userid': log.userid or "",
                        'is_read': log.is_read,
                        'employeeid': log.employeeid or "",
                        'id_application': log.id_application or "",
                    })
            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )

        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)
