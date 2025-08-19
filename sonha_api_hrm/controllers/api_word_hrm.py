from odoo import http
from odoo.http import request, Response, route
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)


class AuthAPIHRM(http.Controller):

    # api tạo làm thêm
    @http.route('/api/create/overtime/<int:employee_id>', type='http', auth='none', methods=['POST'], csrf=False)
    def api_create_overtime(self, employee_id):
        try:
            with request.env.cr.savepoint():
                data = request.httprequest.get_json()

                # Lấy dữ liệu từ request
                department_id = data.get('department_id')
                regis_type = data.get('regis_type')
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

                employee_record = request.env['hr.employee'].sudo().search([('id', 'in', list_emp)], limit=1)
                if not employee_record:
                    raise ValueError("Không tìm thấy nhân viên phù hợp!")
                department_record = request.env['hr.department'].sudo().search([('id', '=', department_id)], limit=1)
                if not department_record:
                    raise ValueError("Không tìm thấy phòng ban phù hợp!")

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
                        "date": str(d.get("date")),
                        "start_time": float_from,
                        "end_time": float_to,
                    }))

                # Chuẩn bị dữ liệu tạo bản ghi
                vals = {
                    'department_id': department_id,
                    'type': regis_type,
                    'date': date_lines,
                    'employee_id': employee,
                    'status': 'draft',
                    'status_lv2': 'draft',
                    'employee_ids': [(6, 0, employees)],
                }

                # Tạo record
                record = request.env['register.overtime.update'].with_user(user_id).sudo().create(vals)

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

    # api get làm thêm
    @http.route('/api/get_overtime/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_overtime(self, id_employee):
        try:
            list_records = request.env['register.overtime.update'].sudo().search([
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
                    if r.type_overtime:
                        if r.status_lv2 == 'draft':
                            state = "Nháp"
                        elif r.status_lv2 == 'waiting':
                            state = "Chờ duyệt cấp 1"
                        elif r.status_lv2 == 'confirm':
                            state = "Chờ duyệt cấp 2"
                        elif r.status_lv2 == 'done':
                            state = "Đã duyệt"
                        else:
                            state = "Hủy"
                    else:
                        if r.status == 'draft':
                            state = "Chờ duyệt"
                        elif r.status == 'done':
                            state = "Đã duyệt"
                    word_slip_data = []
                    for rel in r.date:
                        hours_start = int(rel.start_time)
                        minutes_start = int(round((rel.start_time - hours_start) * 60))
                        time_start = f"{hours_start:02d}:{minutes_start:02d}"

                        hours_end = int(rel.end_time)
                        minutes_end = int(round((rel.end_time - hours_end) * 60))
                        time_end = f"{hours_end:02d}:{minutes_end:02d}"
                        word_slip_data.append({
                            "id": rel.id,
                            "date": str(rel.date) or '',
                            "time_to": time_start or '',
                            "time_from": time_end or '',
                        })

                    if r.type == 'one':
                        data.append({
                            "id": r.id,
                            "status": state,
                            "type": "Tạo cho tôi",
                            "date_sent": str(date_sent),
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
                            "status": state,
                            "type": "Tạo hộ",
                            "date_sent": str(date_sent),
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

    @http.route('/api/get_area_yard', type='http', auth='none', methods=['GET'], csrf=False)
    def get_area_yard(self):
        try:
            data_area = request.env['sonha.area'].sudo().search([])
            data_yard = request.env['sonha.yard'].sudo().search([])
            vals = []
            list_area = []
            list_yard = []
            for area in data_area:
                list_area.append({
                    "id": area.id,
                    "name": area.area
                })
            for yard in data_yard:
                list_yard.append({
                    "id": yard.id,
                    "name": yard.yard,
                    "area": {
                        "id": yard.area.id,
                        "name": yard.area.area
                    }
                })
            vals.append({
                "area": list_area,
                "yard": list_yard
            })
            return Response(
                json.dumps({"success": True, "data": vals}),
                status=200, content_type="application/json"
            )

        except Exception as e:
            return Response(json.dumps(
                {"success": False,
                 "error": str(e)
                 }), content_type="application/json", status=500)

    @http.route('/api/get_detail_overtime/<int:id>/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_detail_overtime(self, id, id_employee):
        try:
            r = request.env['register.overtime.update'].sudo().search([
                ('id', '=', id)
            ])
            employee_id = request.env['hr.employee'].sudo().search([('id', '=', id_employee)])
            data = []
            if r:
                list_employee = [r.employee_id.id] or r.employee_ids.ids
                employee_create = []
                if r.create_uid:
                    create_employee = request.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                    employee_create.append({
                        "id": create_employee.id,
                        "name": create_employee.name,
                    })
                date_sent = r.create_date + relativedelta(hours=7)
                check_button_sent = False
                check_button_done = False
                if r.type_overtime:
                    if r.status_lv2 == 'draft':
                        state = "Nháp"
                    elif r.status_lv2 == 'waiting':
                        state = "Chờ duyệt cấp 1"
                    elif r.status_lv2 == 'confirm':
                        state = "Chờ duyệt cấp 2"
                    elif r.status_lv2 == 'done':
                        state = "Đã duyệt"
                    else:
                        state = "Hủy"

                    if ((id_employee in list_employee) or (r.create_uid.id and employee_id.user_id.id == r.create_uid.id)) and r.status_lv2 == 'draft':
                        check_button_sent = True
                    if ((id_employee == employee_id.parent_id.id) or (id_employee == employee_id.department_id.manager_id.id) or (request.env.user.has_group('sonha_employee.group_manager_employee'))) and (r.status_lv2 != ['draft', 'cancel']):
                        check_button_done = True
                else:
                    if r.status == 'draft':
                        state = "Chờ duyệt"
                    elif r.status == 'done':
                        state = "Đã duyệt"

                    if ((id_employee == employee_id.parent_id.id) or (id_employee == employee_id.department_id.manager_id.id)) and r.status == 'draft':
                        check_button_done = True
                word_slip_data = []
                for rel in r.date:
                    hours_start = int(rel.start_time)
                    minutes_start = int(round((rel.start_time - hours_start) * 60))
                    time_start = f"{hours_start:02d}:{minutes_start:02d}"

                    hours_end = int(rel.end_time)
                    minutes_end = int(round((rel.end_time - hours_end) * 60))
                    time_end = f"{hours_end:02d}:{minutes_end:02d}"
                    word_slip_data.append({
                        "id": rel.id,
                        "date": str(rel.date) or '',
                        "time_to": time_start or '',
                        "time_from": time_end or '',
                    })

                if r.type == 'one':
                    data.append({
                        "id": r.id,
                        "department_id": {
                            "id": r.department_id.id,
                            "name": r.department_id.name,
                        },
                        "status": state,
                        "regis_type": "Tạo cho tôi",
                        "type": "Làm thêm",
                        "date_sent": str(date_sent),
                        "date": word_slip_data,
                        "employee_id": {
                            "id": r.employee_id.id,
                            "name": r.employee_id.name
                        },
                        "employee_create": employee_create,
                        "button_sent": check_button_sent,
                        "button_done": check_button_done,
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
                            "id": r.department_id.id,
                            "name": r.department_id.name,
                        },
                        "status": state,
                        "regis_type": "Tạo hộ",
                        "type": "Làm thêm",
                        "date_sent": str(date_sent),
                        "date": word_slip_data,
                        "employee_id": list_employee,
                        "employee_create": employee_create,
                        "button_sent": check_button_sent,
                        "button_done": check_button_done,
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

    @http.route('/api/change_status/overtime/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_change_status_overtime(self, id):
        try:
            record = request.env['register.overtime.update'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            if not record.type_overtime:
                record.status = 'done'
            else:
                if record.status_lv2 == 'draft':
                    record.status_lv2 = 'waiting'
                elif record.status_lv2 == 'waiting':
                    record.status_lv2 = 'confirm'
                elif record.status_lv2 == 'confirm':
                    record.status_lv2 = 'done'

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

    @http.route('/api/back_status/overtime/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def api_back_status_overtime(self, id):
        try:
            record = request.env['register.overtime.update'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            if not record.type_overtime:
                record.status = 'draft'
            else:
                record.status_lv2 = 'draft'

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

    @http.route('/api/get_overtime_manager/<int:id_employee>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_overtime_manager(self, id_employee):
        try:
            list_records = request.env['register.overtime.update'].sudo().search([
                '|',
                ('status', '=', 'draft'),
                ('status_lv2', '=', 'waiting'),
            ])
            manager = request.env['hr.employee'].sudo().browse(id_employee)
            data = []

            def prepare_employee_create(record):
                """Lấy thông tin người tạo"""
                if not record.create_uid:
                    return []
                emp = request.env['hr.employee'].sudo().search([('user_id', '=', record.create_uid.id)], limit=1)
                return [{"id": emp.id, "name": emp.name}]

            def prepare_slip_data(record):
                """Lấy danh sách giờ bắt đầu - kết thúc"""
                slips = []
                for slip in record.date:
                    hs, ms = divmod(int(round(slip.start_time * 60)), 60)
                    he, me = divmod(int(round(slip.end_time * 60)), 60)
                    slips.append({
                        "id": slip.id,
                        "date": str(slip.date) or '',
                        "time_to": f"{hs:02d}:{ms:02d}",
                        "time_from": f"{he:02d}:{me:02d}",
                    })
                return slips

            def append_record(record, slips, emp_create):
                """Đưa record vào danh sách data"""
                base = {
                    "id": record.id,
                    "status": "Chờ duyệt",
                    "date_sent": str(record.create_date + relativedelta(hours=7)),
                    "type": "Làm thêm",
                    "date": slips,
                    "employee_create": emp_create
                }
                if record.type == 'one':
                    base.update({
                        "regis_type": "Tạo cho tôi",
                        "employee_id": {
                            "id": record.employee_id.id,
                            "name": record.employee_id.name
                        }
                    })
                else:
                    base.update({
                        "regis_type": "Tạo hộ",
                        "employee_id": [
                            {"id": emp.id, "name": emp.name}
                            for emp in record.employee_ids
                        ]
                    })
                data.append(base)

            def is_manager_of(record):
                """Kiểm tra có phải quản lý hợp lệ không"""
                return (
                        (record.employee_id and record.employee_id.parent_id.id == manager.id) or
                        (record.employee_ids and record.employee_ids[0].parent_id.id == manager.id) or
                        (record.department_id.manager_id.id == manager.id) or
                        (record.type_overtime and manager.user_id.has_group('sonha_employee.group_manager_employee'))
                )

            for r in list_records:
                if not is_manager_of(r):
                    continue
                emp_create = prepare_employee_create(r)
                slips = prepare_slip_data(r)
                append_record(r, slips, emp_create)

            return Response(
                json.dumps({"success": True, "data": data}),
                status=200, content_type="application/json"
            )

        except Exception as e:
            return Response(json.dumps(
                {"success": False, "error": str(e)}
            ), content_type="application/json", status=500)
