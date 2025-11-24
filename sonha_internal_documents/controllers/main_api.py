from odoo import http
from odoo.http import request, Response, route
import json
from datetime import datetime
import base64
from dateutil.relativedelta import relativedelta
from datetime import timedelta
import logging
_logger = logging.getLogger(__name__)


class APIVanBan(http.Controller):

    @http.route('/api/get/danh_muc_van_ban', type='http', auth='none', methods=['GET'], csrf=False)
    def get_danh_muc_van_ban(self):
        try:
            list_records = request.env['dk.loai.vb'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "ma": r.ma,
                        "ten": r.ten
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

    @http.route('/api/get/tien_trinh_xu_ly', type='http', auth='none', methods=['GET'], csrf=False)
    def get_tien_trinh_xu_ly(self):
        try:
            list_records = request.env['dk.xu.ly'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "ma": r.ma,
                        "ten": r.ten,
                        "stt": r.stt
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

    @http.route('/api/get/danh_sach_nguoi_duyet', type='http', auth='none', methods=['GET'], csrf=False)
    def get_danh_sach_nguoi_duyet(self):
        try:
            list_records = request.env['res.users'].sudo().search([])
            data = []
            if list_records:
                for r in list_records:
                    data.append({
                        "id": r.id,
                        "ten": r.name
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

    @http.route('/api/get/danh_sach_don_vi/<int:id_user>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_danh_sach_don_vi(self, id_user):
        try:
            if not id_user:
                raise ValueError("Không có id người đăng nhập")
            user_id = request.env['res.users'].sudo().search([('id', '=', id_user)])
            if not user_id:
                raise ValueError("Không tìm thấy dữ liệu người đăng nhập")
            data = []
            for r in user_id.company_ids:
                data.append({
                    "id": r.id,
                    "ten": r.name
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

    @http.route('/api/create/tao_van_ban/<int:user_id>', type='http', auth='none', methods=['POST'], csrf=False)
    def api_tao_van_ban(self, user_id):
        try:
            with request.env.cr.savepoint():
                data = request.httprequest.get_json()

                # Lấy dữ liệu từ request
                ngay_lam_don = data.get('ngay_lam_don')
                so_don = data.get('so_don')
                loai_van_ban = data.get('loai_van_ban')
                don_vi = data.get('don_vi')
                noi_dung = data.get('noi_dung')
                data_xu_ly = data.get('luong_xu_ly', [])
                tong_ngay_bp = data.get('tong_ngay_bp')
                tong_ngay_bdh = data.get('tong_ngay_bdh')
                tong_ngay_ct = data.get('tong_ngay_ct')
                so_ngay_pb = data.get('so_ngay_pb')
                so_ngay_bdh = data.get('so_ngay_bdh')
                so_ngay_ct = data.get('so_ngay_ct')
                data_file = data.get('danh_sach_file', [])
                required_fields = {
                    'ngay_lam_don': ngay_lam_don,
                    'so_don': so_don,
                    'loai_van_ban': loai_van_ban,
                    'don_vi': don_vi,
                    'noi_dung': noi_dung,
                    'luong_xu_ly': data_xu_ly,
                    'tong_ngay_bp': tong_ngay_bp,
                    'tong_ngay_bdh': tong_ngay_bdh,
                    'tong_ngay_ct': tong_ngay_ct,
                    'so_ngay_pb': so_ngay_pb,
                    'so_ngay_bdh': so_ngay_bdh,
                    'so_ngay_ct': so_ngay_ct,
                }

                # Chạy vòng lặp check toàn bộ
                for field, value in required_fields.items():
                    if value is None or value == "" or value == []:
                        raise ValueError(f"Thiếu dữ liệu '{field}' trong body API!")
                if not user_id:
                    raise ValueError("Không có dữ liệu người đăng nhập!")
                user_id = request.env['res.users'].sudo().search([('id', '=', user_id)])
                date_lines = []
                for d in data_xu_ly:
                    date_lines.append((0, 0, {
                        "user_duyet": int(d.get("nguoi_duyet")),
                        "xu_ly": int(d.get("tien_trinh")),
                        "sn_duyet": d.get("sn_duyet") if d.get("sn_duyet") else None,
                    }))
                date_file = []
                for f in data_file:
                    date_file.append((0, 0, {
                        "file": str(f.get("file")),
                        "file_name": str(f.get("ten_file"))
                    }))

                # Chuẩn bị dữ liệu tạo bản ghi
                vals = {
                    'ngay_ct': str(ngay_lam_don),
                    'chung_tu': so_don,
                    'dvcs': int(don_vi),
                    'id_loai_vb': int(loai_van_ban),
                    'noi_dung': noi_dung,
                    'tn_pb': tong_ngay_bp,
                    'sn_pb': so_ngay_pb,
                    'tn_bdh': tong_ngay_bdh,
                    'sn_bdh': so_ngay_bdh,
                    'tn_ct': tong_ngay_ct,
                    'sn_ct': so_ngay_ct,
                    'dk_vb_d': date_lines,
                    'file_ids': date_file
                }

                # Tạo record
                record = request.env['dk.vb.h'].with_user(user_id).sudo().create(vals)

                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id
                }), content_type="application/json", status=200)

        except Exception as e:
            request.env.cr.rollback()
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/get/chi_tiet_van_ban/<int:id>/<int:user_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_chi_tiet_van_ban(self, id, user_id):
        try:
            user_id = request.env['res.users'].browse(user_id)
            record = request.env['dk.vb.h'].with_context(show_all=True).sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy dữ liệu bản ghi")
            if not user_id:
                raise ValueError("Không tìm thấy dữ liệu nhân viên đang đăng nhập")

            if record.status == 'reject':
                trang_thai = "Từ chối"
            elif record.status == 'draft':
                trang_thai = "Nháp"
            else:
                trang_thai = "Đã xin phê duyệt"
            data = []
            date_lines = []
            for d in record.dk_vb_d:
                if d.ngay_duyet:
                    sttus  = "Đã duyệt"
                else:
                    sttus = "Chưa duyệt"
                date_lines.append({
                    'id': d.id,
                    'nguoi_duyet': {
                        'id': d.user_duyet.id,
                        'ten': d.user_duyet.name
                    },
                    'tien_trinh': {
                        'id': d.xu_ly.id,
                        'ten': d.xu_ly.ten
                    },
                    'sn_duyet': d.sn_duyet,
                    'ngay_duyet': str(d.ngay_duyet),
                    'tu_choi': d.tu_choi or "",
                    'trang_thai_tien_trinh': sttus,
                })

            data_file = []
            for f in record.file_ids:
                data_file.append({
                    'ten': f.file_name,
                    'file_base64': base64.b64encode(f.file).decode('utf-8') if f.file else False,
                })

            if record.check_write == True or record.create_uid.id != user_id.id:
                nut_xin_phe_duyet = False
            else:
                nut_xin_phe_duyet = True

            data.append({
                'id': record.id,
                'ngay_lam_don': str(record.ngay_ct) or "",
                'so_don': record.chung_tu,
                'don_vi': {
                    'id': record.dvcs.id,
                    'ten': record.dvcs.name,
                },
                'loai_vb': {
                    'id': record.id_loai_vb.id,
                    'ten': record.id_loai_vb.ten,
                },
                'ngay_hoan_thanh': str(record.ngay_ht) or "",
                'noi_dung': record.noi_dung,
                'tien_trinh_xu_ly': date_lines,
                'danh_sach_file': data_file,
                'tong_ngay_pb': record.tn_pb,
                'so_ngay_pb': record.sn_pb,
                'tong_ngay_bdh': record.tn_bdh,
                'so_ngay_bdh': record.sn_bdh,
                'tong_ngay_ct': record.tn_ct,
                'so_ngay_ct': record.sn_ct,
                'trang_thai': trang_thai,
                'xin_phe_duyet': nut_xin_phe_duyet,

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

    @http.route('/api/get/danh_sach_cua_toi/<int:user_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_danh_sach_cua_toi(self, user_id):
        try:
            user = request.env['res.users'].sudo().search([('id', '=', user_id)])
            if not user:
                raise ValueError("Không tìm thấy dữ liệu nhân viên đang đăng nhập!")
            data = []
            if user.has_group('sonha_internal_documents.group_admin_van_ban'):
                records = request.env['dk.vb.h'].with_context(show_all=True).sudo().search([], order="id desc")
            else:
                records = request.env['dk.vb.h'].with_context(show_all=True).sudo().search([('create_uid', '=', user.id)], order="id desc")

            for r in records:
                if r.status == 'reject':
                    trang_thai = "Từ chối"
                elif r.status == 'draft':
                    trang_thai = "Nháp"
                else:
                    trang_thai = "Đã xin phê duyệt"
                data.append({
                    'id': r.id,
                    'so_don': r.chung_tu,
                    'ngay_lam_don': str(r.ngay_ct),
                    'dvcs': {
                        'id': r.dvcs.id,
                        'ten': r.dvcs.name,
                    },
                    'ngay_hoan_thanh': str(r.ngay_ht),
                    'loai_vb': {
                        'id': r.id_loai_vb.id,
                        'ten': r.id_loai_vb.ten,
                    },
                    'trang_thai': trang_thai,
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

    @http.route('/api/get/danh_sach_cho_duyet/<int:user_id>', type='http', auth='none', methods=['GET'], csrf=False)
    def get_danh_sach_cho_duyet(self, user_id):
        try:
            user = request.env['res.users'].sudo().search([('id', '=', user_id)])
            if not user:
                raise ValueError("Không tìm thấy dữ liệu nhân viên đang đăng nhập!")
            query = "SELECT * FROM fn_lay_vb_duyet_app(%s, %s, %s)"
            request.env.cr.execute(query, (user_id, 2, 1))
            rows = request.env.cr.dictfetchall()
            ids = [row['id'] for row in rows if 'id' in row]
            records = request.env['dk.vb.h'].sudo().search([('id', 'in', ids)], order="id desc")
            data = []

            for r in records:
                if r.status == 'reject':
                    trang_thai = "Từ chối"
                elif r.status == 'draft':
                    trang_thai = "Nháp"
                else:
                    trang_thai = "Đã xin phê duyệt"
                data.append({
                    'id': r.id,
                    'so_don': r.chung_tu,
                    'ngay_lam_don': str(r.ngay_ct),
                    'dvcs': {
                        'id': r.dvcs.id,
                        'ten': r.dvcs.name,
                    },
                    'ngay_hoan_thanh': str(r.ngay_ht),
                    'loai_vb': {
                        'id': r.id_loai_vb.id,
                        'ten': r.id_loai_vb.ten,
                    },
                    'trang_thai': trang_thai,
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

    @http.route('/api/duyet_tien_trinh/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def duyet_tien_trinh(self, id):
        try:
            record = request.env['dk.vb.d'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            else:
                record.ngay_duyet = datetime.now()
                record.is_approved = True
                record.fill_ngay_bd_duyet(record)
                # Trả về kết quả
                return Response(json.dumps({
                    "success": True,
                    "id": record.id,
                    "msg": "Bấm nút thành công",
                }), content_type="application/json", status=200)

        except Exception as e:
            request.env.cr.rollback()
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

    @http.route('/api/tu_choi_tien_trinh/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def tu_choi_tien_trinh(self, id):
        try:
            data = request.httprequest.get_json()
            ly_do_tu_choi = data.get('ly_do_tu_choi')
            record = request.env['dk.vb.d'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")
            record.is_approved = False
            old_value = record.tu_choi or ""
            record.tu_choi = old_value + f"{ly_do_tu_choi}\n"
            record.dk_vb_h.nguoi_tu_choi = record.user_duyet.id
            record.dk_vb_h.check_write = False
            record.dk_vb_h.status = 'reject'

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

    @http.route('/api/xin_phe_duyet/<int:id>', type='http', auth='none', methods=['PUT'], csrf=False)
    def xin_phe_duyet(self, id):
        try:
            record = request.env['dk.vb.h'].sudo().search([('id', '=', id)])
            if not record:
                raise ValueError("Không tìm thấy bản ghi")

            record.func_xu_ly_duyet(record)

            return Response(json.dumps({
                "success": True,
                "id": record.id,
                "msg": "Bấm nút thành công",
            }), content_type="application/json", status=200)

        except Exception as e:
            request.env.cr.rollback()
            return Response(json.dumps({
                "success": False,
                "error": str(e)
            }), content_type="application/json", status=500)

