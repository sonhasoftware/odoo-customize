from odoo import api, fields, models
import unicodedata
import re
import json
from collections import Counter
import math
from odoo.exceptions import ValidationError
import requests


class MDMKhachHang(models.Model):
    _name = 'mdm.khach.hang'

    ma_khach = fields.Char("Mã", store=True)
    ten_khach = fields.Char("Tên", store=True, required=True)
    dia_chi_khach = fields.Char("Địa chỉ khách", store=True)
    ma_cn = fields.Many2one('mdm.chi.nhanh', "Mã Chi nhánh")
    nhom_khach = fields.Many2one('mdm.nhom.khach', "Nhóm khách")
    ten_salesman = fields.Many2one('mdm.saleman', "Tên Salesman")
    ma_salesman = fields.Char(related='ten_salesman.ma', string="Mã Salesman")
    ma_dms = fields.Char("Mã DMS", store=True)
    ma_tinh = fields.Many2one('mdm.tinh', "Mã tỉnh")
    kinh_do = fields.Char("Kinh độ", store=True)
    vi_do = fields.Char("Vĩ độ", store=True)
    so_dien_thoai = fields.Char("Số điện thoại", store=True, required=True)
    dat_nuoc = fields.Many2one('mdm.quoc.gia', "Đất nước")
    khu_vuc = fields.Many2one('mdm.khu.vuc', "Khu vực")
    vung = fields.Char("Vùng", store=True)
    qlv = fields.Many2one('mdm.quan.ly.vung', "QLV")
    mst = fields.Char("MST", store=True)
    vector_mst = fields.Text("Vector MST", compute="_compute_vector", store=True)
    vector_ten = fields.Text("Vector Tên", compute="_compute_vector", store=True)
    vector_dia_chi = fields.Text("Vector địa chỉ", compute="_compute_vector", store=True)
    vector_sdt = fields.Text("Vector sđt", compute="_compute_vector", store=True)
    so_sanh_khach_hang = fields.One2many('ket.qua.khach.hang', 'key_kh', string="Chi tiết")
    cccd = fields.Char("CCCD", store=True)
    vector_cccd = fields.Text("Vector cccd", compute="_compute_vector", store=True)
    dvcs = fields.Many2one('res.company', string="ĐV", store=True, default=lambda self: self.env.company, readonly=False)
    luong_duyet = fields.Many2one('luong.duyet', "Luồng duyệt")

    buoc_duyet = fields.One2many('buoc.duyet.khach.hang', 'key', string="Bước duyệt")

    current_step = fields.Integer(string="STT hiện tại", default=1)
    can_approve = fields.Boolean(compute='_compute_can_approve')


    def _compute_can_approve(self):
        for rec in self:
            user = self.env.user

            steps = rec.buoc_duyet.filtered(
                lambda x: x.sequence == rec.current_step
            )

            rec.can_approve = any(
                step.ten_nguoi_duyet.id == user.id and not step.da_duyet
                for step in steps
            )

    def action_approve(self):
        for rec in self:
            user = self.env.user

            # lấy tất cả step hiện tại (cùng sequence)
            steps = rec.buoc_duyet.filtered(
                lambda x: x.sequence == rec.current_step
            )

            # tìm dòng của user hiện tại
            my_step = steps.filtered(
                lambda x: x.ten_nguoi_duyet.id == user.id
            )[:1]

            if not my_step:
                raise ValidationError("Chưa đến bước bạn duyệt")

            # ✔ duyệt dòng của mình
            my_step.da_duyet = True

            # 🔥 kiểm tra tất cả đã duyệt chưa
            all_done = all(step.da_duyet for step in steps)

            # 👉 nếu tất cả đã duyệt → mới sang step tiếp theo
            if all_done:
                rec.current_step += 1

    @api.onchange('luong_duyet')
    def _get_buoc_duyet(self):
        for r in self:
            if not r.luong_duyet:
                r.buoc_duyet = [(5, 0, 0)]
                return

            # XÓA dữ liệu cũ
            lines = [(5, 0, 0)]

            data = r.luong_duyet.sudo().step_ids.sorted('sequence')

            for step in data:
                if step.phuong_thuc == 'ql':
                    lines.append((0, 0, {
                        'sequence': step.sequence,
                        'phuong_thuc': step.phuong_thuc,
                        'vai_tro': step.vai_tro.id,
                        'ten_nguoi_duyet': 2,
                    }))
                else:
                    for user in step.ten_nguoi_duyet:
                        lines.append((0, 0, {
                            'sequence': step.sequence,
                            'phuong_thuc': step.phuong_thuc,
                            'vai_tro': step.vai_tro.id,
                            'ten_nguoi_duyet': user.id,
                        }))

            r.buoc_duyet = lines

    @api.constrains('mst', 'cccd')
    def _check_no_space_fields(self):
        for record in self:
            if record.mst and ' ' in record.mst:
                raise ValidationError("Mã số thuế không được chứa khoảng trắng!")

            if record.cccd and ' ' in record.cccd:
                raise ValidationError("CCCD không được chứa khoảng trắng!")

            if not record.mst and not record.cccd:
                raise ValidationError("Phải nhập dữ lệu MST hoặc CCCD")

    @api.constrains('so_dien_thoai')
    def _check_phone(self):
        for record in self:
            if record.so_dien_thoai:
                # Không có khoảng trắng + đúng 10 số
                if not re.fullmatch(r'\d{10}', record.so_dien_thoai):
                    raise ValidationError("Số điện thoại phải đúng 10 chữ số và không chứa khoảng trắng!")

    @api.depends('ten_khach', 'dia_chi_khach', 'so_dien_thoai', 'mst', 'cccd')
    def _compute_vector(self):
        for record in self:
            if record.ten_khach:
                vec_dict = record._name_to_vector(record.ten_khach)
                record.vector_ten = json.dumps(vec_dict)
            else:
                record.vector_ten = False

            if record.mst:
                vec_dict = record._name_to_vector(record.mst)
                record.vector_mst = json.dumps(vec_dict)
            else:
                record.vector_mst = False

            if record.dia_chi_khach:
                vec_dict = record._name_to_vector(record.dia_chi_khach)
                record.vector_dia_chi = json.dumps(vec_dict)
            else:
                record.vector_dia_chi = False

            if record.so_dien_thoai:
                vec_dict = record._name_to_vector(record.so_dien_thoai)
                record.vector_sdt = json.dumps(vec_dict)
            else:
                record.vector_sdt = False

            if record.cccd:
                vec_dict = record._name_to_vector(record.cccd)
                record.vector_cccd = json.dumps(vec_dict)
            else:
                record.vector_cccd = False

    def _normalize_name(self, text):
        text = (text or "").lower()
        text = unicodedata.normalize('NFD', text)
        text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _name_to_vector(self, text, n=2):
        text = self._normalize_name(text).replace(" ", "")
        if len(text) < n:
            return {}

        ngrams = [text[i:i + n] for i in range(len(text) - n + 1)]
        return dict(Counter(ngrams))

    def get_vector_khach_hang(self):
        data = self.search([])
        for record in data:
            if record.ten_khach:
                vec_dict = record._name_to_vector(record.ten_khach)
                record.vector_ten = json.dumps(vec_dict)
            else:
                record.vector_ten = False

            if record.mst:
                vec_dict = record._name_to_vector(record.mst)
                record.vector_mst = json.dumps(vec_dict)
            else:
                record.vector_mst = False

            if record.dia_chi_khach:
                vec_dict = record._name_to_vector(record.dia_chi_khach)
                record.vector_dia_chi = json.dumps(vec_dict)
            else:
                record.vector_dia_chi = False

            if record.so_dien_thoai:
                vec_dict = record._name_to_vector(record.so_dien_thoai)
                record.vector_sdt = json.dumps(vec_dict)
            else:
                record.vector_sdt = False

            if record.cccd:
                vec_dict = record._name_to_vector(record.cccd)
                record.vector_cccd = json.dumps(vec_dict)
            else:
                record.vector_cccd = False

    def _cosine_similarity_dict(self, vec1, vec2):
        dot = 0.0

        # dot product
        for key in vec1:
            if key in vec2:
                dot += vec1[key] * vec2[key]

        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot / (norm1 * norm2)

    def create_write_action_data(self, record):
        if not record.vector_ten or not record.vector_sdt:
            return record

        # or not record.vector_sdt or not record.vector_mst
        if record.vector_ten:
            new_vec_ten = json.loads(record.vector_ten)
        else:
            new_vec_ten = None
        if record.vector_mst:
            new_vec_mst = json.loads(record.vector_mst)
        else:
            new_vec_mst = None
        if record.vector_sdt:
            new_vec_sdt = json.loads(record.vector_sdt)
        else:
            new_vec_sdt = None
        if record.vector_cccd:
            new_vec_cccd = json.loads(record.vector_cccd)
        else:
            new_vec_cccd = None

        logs = []
        offset = 0
        limit = 5000

        while True:
            batch = self.sudo().search_read(
                [('id', '!=', record.id)],
                ['id', 'vector_sdt', 'vector_ten', 'vector_mst', 'vector_cccd', 'ma_khach', 'ten_khach'],
                offset=offset,
                limit=limit
            )

            if not batch:
                break

            for r in batch:
                if r['vector_ten']:
                    old_vec_ten = json.loads(r['vector_ten'])
                else:
                    old_vec_ten = None
                if r['vector_mst']:
                    old_vec_mst = json.loads(r['vector_mst'])
                else:
                    old_vec_mst = None
                if r['vector_sdt']:
                    old_vec_sdt = json.loads(r['vector_sdt'])
                else:
                    old_vec_sdt = None
                if r['vector_cccd']:
                    old_vec_cccd = json.loads(r['vector_cccd'])
                else:
                    old_vec_cccd = None

                score_ten = score_sdt = score_mst = score_cccd = 0

                if new_vec_ten and old_vec_ten:
                    score_ten = self._cosine_similarity_dict(new_vec_ten, old_vec_ten)
                if new_vec_sdt and old_vec_sdt:
                    score_sdt = self._cosine_similarity_dict(new_vec_sdt, old_vec_sdt)
                if new_vec_mst and old_vec_mst:
                    score_mst = self._cosine_similarity_dict(new_vec_mst, old_vec_mst)
                if new_vec_cccd and old_vec_cccd:
                    score_cccd = self._cosine_similarity_dict(new_vec_cccd, old_vec_cccd)

                # if score_mst and score_mst > 0.99:
                #     raise ValidationError("MST đã trùng 100% không thể tạo dữ liệu")
                # if score_cccd and score_cccd >= 1:
                #     raise ValidationError("CCCD đã trùng 100% không thể tạo dữ liệu")

                if (score_ten and score_ten >= 0.8) or (score_sdt and score_sdt >= 0.6) or (score_mst and score_mst >= 0.9) or (score_cccd and score_cccd >= 0.9):
                    logs.append({
                        'key_kh': record.id,
                        'record': r['id'],
                        'ten_khach': r['ten_khach'],
                        'score_ten': score_ten * 100 if score_ten else 0,
                        'score_mst': score_mst * 100 if score_mst else 0,
                        'score_sdt': score_sdt * 100 if score_sdt else 0,
                        'score_cccd': score_cccd * 100 if score_cccd else 0
                    })

            offset += limit
        self.env['ket.qua.khach.hang'].sudo().search([('key_kh', '=', record.id)]).unlink()
        if logs:
            self.env['ket.qua.khach.hang'].sudo().create(logs)

    def action_open_update_popup(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Nhập thêm thông tin',
            'res_model': 'mdm.khach.hang',
            'view_mode': 'form',
            'view_id': self.env.ref('sonha_mdm.view_mdm_khach_hang_update_form').id,
            'res_id': self.id,
            'target': 'new'
        }

    def action_save_popup(self):
        for r in self:
            self.create_write_action_data(r)
        return {'type': 'ir.actions.act_window_close'}

    def write(self, vals):
        res = super().write(vals)
        for r in self:
            self.create_write_action_data(r)
            self.call_api_update(r)
        return res

    def action_confirm_data(self):
        for r in self:
            self.create_write_action_data(r)

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self.create_write_action_data(record)
        self.call_api_insert(record)

        return record

    def call_api_insert(self, record):
        data = {
            "cccd": record.cccd or None,
            "mst": record.mst or None,
            "so_dien_thoai": record.so_dien_thoai or None,
            "ten_khach": record.ten_khach or None,
            "ma_khach": record.ma_khach or None,
            "dia_chi_khach": record.dia_chi_khach or None,
            "ma_cn": record.ma_cn.ma or None,
            "ten_cn": record.ma_cn.ten or None,
            "ma_nhom_khach": record.nhom_khach.ma or None,
            "ten_nhom_khach": record.nhom_khach.ten or None,
            "ten_salesman": record.ten_salesman.ten or None,
            "ma_salesman": record.ten_salesman.ma or None,
            "ma_dms": record.ma_dms or None,
            "ma_tinh": record.ma_tinh.ma or None,
            "ten_tinh": record.ma_tinh.ten or None,
            "kinh_do": record.kinh_do or None,
            "vi_do": record.vi_do or None,
            "ten_dat_nuoc": record.dat_nuoc.ten or None,
            "ma_dat_nuoc": record.dat_nuoc.ma or None,
            "ten_khu_vuc": record.khu_vuc.ten or None,
            "ma_khu_vuc": record.khu_vuc.ma or None,
            "vung": record.vung or None,
            "ten_qlv": record.qlv.ten or None,
            "ma_qlv": record.qlv.ma or None,
            "ma_dvcs": record.dvcs.company_code or None,
            "ten_dvcs": record.dvcs.name or None,
            "type": "insert"
        }

        # 👉 convert sang JSON string
        json_str = json.dumps(data, ensure_ascii=False)

        # 🔥 thêm dấu ' 2 bên (theo yêu cầu API của bạn)
        payload = f"'{json_str}'"

        try:
            response = requests.put(
                "https://bhapi.sonha.com.vn/api/mdm_kh",
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8'
                },
                timeout=10
            )

            # debug
            print("API RESPONSE:", response.text)

        except Exception as e:
            print("API ERROR:", str(e))

    def call_api_update(self, record):
        data = {
            "cccd": record.cccd or None,
            "mst": record.mst or None,
            "so_dien_thoai": record.so_dien_thoai or None,
            "ten_khach": record.ten_khach or None,
            "ma_khach": record.ma_khach or None,
            "dia_chi_khach": record.dia_chi_khach or None,
            "ma_cn": record.ma_cn.ma or None,
            "ten_cn": record.ma_cn.ten or None,
            "ma_nhom_khach": record.nhom_khach.ma or None,
            "ten_nhom_khach": record.nhom_khach.ten or None,
            "ten_salesman": record.ten_salesman.ten or None,
            "ma_salesman": record.ten_salesman.ma or None,
            "ma_dms": record.ma_dms or None,
            "ma_tinh": record.ma_tinh.ma or None,
            "ten_tinh": record.ma_tinh.ten or None,
            "kinh_do": record.kinh_do or None,
            "vi_do": record.vi_do or None,
            "ten_dat_nuoc": record.dat_nuoc.ten or None,
            "ma_dat_nuoc": record.dat_nuoc.ma or None,
            "ten_khu_vuc": record.khu_vuc.ten or None,
            "ma_khu_vuc": record.khu_vuc.ma or None,
            "vung": record.vung or None,
            "ten_qlv": record.qlv.ten or None,
            "ma_qlv": record.qlv.ma or None,
            "ma_dvcs": record.dvcs.company_code or None,
            "ten_dvcs": record.dvcs.name or None,
            "type": "update"
        }

        # 👉 convert sang JSON string
        json_str = json.dumps(data, ensure_ascii=False)

        # 🔥 thêm dấu ' 2 bên (theo yêu cầu API của bạn)
        payload = f"'{json_str}'"

        try:
            response = requests.put(
                "https://bhapi.sonha.com.vn/api/mdm_kh",
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8'
                },
                timeout=10
            )

            # debug
            print("API RESPONSE:", response.text)

        except Exception as e:
            print("API ERROR:", str(e))


