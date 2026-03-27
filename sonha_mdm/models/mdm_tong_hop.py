from odoo import api, fields, models
import unicodedata
import re
import json
from collections import Counter
import math
from odoo.exceptions import ValidationError
import requests


class MDMTongHop(models.Model):
    _name = 'mdm.tong.hop'

    ma = fields.Char("Mã")
    ma_tg = fields.Char("Mã TG")
    mdm_hh_type_id = fields.Many2one('mdm.hh.type', string="Loại hàng hóa")
    mdm_hh_type = fields.Text(related='mdm_hh_type_id.ten', string="Loại hàng hóa")
    material = fields.Char("Material Des.VI")
    ten_ngan = fields.Char("Tên ngắn")
    ten = fields.Char("Tên")
    material_number = fields.Char("Material number")
    dvt = fields.Char("Đơn vị tính")
    material_group = fields.Integer("Material Group")
    batch_management = fields.Char("Batch Management")

    mch1 = fields.Integer("MCH1")
    mch2 = fields.Integer("MCH2")
    mch3 = fields.Integer("MCH3")
    mch4 = fields.Integer("MCH4")
    division = fields.Integer("Division")
    commodity_industry = fields.Char("...")
    product_hierarchy = fields.Char("Product hierarchy")
    description = fields.Char("Description")
    gross_weight = fields.Char("Gross weight")
    net_weight = fields.Char("Net weight")
    weight_unit = fields.Char("Weight Unit")

    volume = fields.Char("Volume")
    volume_unit = fields.Char("Volume Unit")
    size = fields.Char("Size")

    chung_loai1 = fields.Many2one('mdm.chung.loai1', string="Chủng loại 1")
    chung_loai2 = fields.Many2one('mdm.chung.loai2', string="Chủng loại 2")
    linh_vuc = fields.Many2one('mdm.linh.vuc', string="Lĩnh vực")
    nganh_hang = fields.Many2one('mdm.nganh.hang', string="Ngành hàng")
    nhan_hang = fields.Many2one('mdm.nhan.hang', string="Nhãn hàng")
    chat_lieu = fields.Many2one('mdm.chat.lieu', string="Chất liệu")
    do_bong = fields.Many2one('mdm.do.bong', string="Độ bóng")
    do_day = fields.Many2one('mdm.do.day', string="Độ dày")
    dung_tich = fields.Many2one('mdm.dung.tich', string="Dung tích")

    key_linh_vuc = fields.Integer(related='chung_loai2.key_linh_vuc', string="Key lĩnh vực")
    key_nganh_hang = fields.Integer(related='chung_loai2.key_nganh_hang', string="Key ngành hàng")
    key_nhan_hang = fields.Integer(related='chung_loai2.key_nhan_hang', string="Key nhãn hàng")

    vector = fields.Text("Vector", compute="_compute_vector", store=True)
    vector_group = fields.Text("Vector", compute="_compute_vector_group", store=True)

    so_sanh = fields.One2many('ket.qua.tong.hop', 'mdm', string="Chi tiết")
    dvcs = fields.Many2one('res.company', string="ĐV", store=True, default=lambda self: self.env.company, readonly=False)
    luong_duyet = fields.Many2one('luong.duyet', string="Luồng duyệt")
    buoc_duyet = fields.One2many('buoc.duyet.hang.hoa', 'key', string="Bước duyệt")

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


    @api.constrains('chung_loai1', 'chung_loai2', 'linh_vuc', 'nganh_hang', 'nhan_hang', 'key_linh_vuc', 'key_nganh_hang', 'key_nhan_hang')
    def _check_chung_loai(self):
        for record in self:
            if record.chung_loai2 and record.chung_loai2.key != record.chung_loai1:
                raise ValidationError(
                    "Chủng loại 2 không thuộc Chủng loại 1 đã chọn."
                )
            if record.linh_vuc and record.key_linh_vuc and record.linh_vuc.key_map != record.key_linh_vuc:
                raise ValidationError(
                    "Lĩnh vực không thuộc Chủng loại 2 đã chọn."
                )
            if record.nganh_hang and record.key_nganh_hang and record.nganh_hang.key_map != record.key_nganh_hang:
                raise ValidationError(
                    "Ngành hàng không thuộc Chủng loại 2 đã chọn."
                )
            if record.nhan_hang and record.key_nhan_hang and record.nhan_hang.key_map != record.key_nhan_hang:
                raise ValidationError(
                    "Nhãn hàng không thuộc Chủng loại 2 đã chọn."
                )

    @api.onchange(
        'chung_loai1',
        'chung_loai2',
        'linh_vuc',
        'nganh_hang',
        'nhan_hang'
        'key_linh_vuc',
        'key_nganh_hang',
        'key_nhan_hang'
    )
    def _onchange_validate_domain(self):
        for record in self:

            if record.chung_loai2 and record.chung_loai2.key != record.chung_loai1:
                record.chung_loai2 = False
                record.linh_vuc = False
                record.nganh_hang = False
                record.nhan_hang = False

            if record.linh_vuc and record.key_linh_vuc and record.linh_vuc.key_map != record.key_linh_vuc:
                record.linh_vuc = False

            if record.nganh_hang and record.key_nganh_hang and record.nganh_hang.key_map != record.key_nganh_hang:
                record.nganh_hang = False

            if record.nhan_hang and record.key_nhan_hang and record.nhan_hang.key_map != record.key_nhan_hang:
                record.nhan_hang = False

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

    @api.depends('ten')
    def _compute_vector(self):
        for record in self:
            if record.ten:
                vec_dict = record._name_to_vector(record.ten)
                record.vector = json.dumps(vec_dict)
            else:
                record.vector = False

    @api.depends('chung_loai1', 'chung_loai2', 'linh_vuc', 'nganh_hang', 'nhan_hang')
    def _compute_vector_group(self):
        for record in self:
            text = (
                    ((record.chung_loai1.ten if record.chung_loai1 else "") or "") +
                    ((record.chung_loai2.ten if record.chung_loai2 else "") or "") +
                    ((record.linh_vuc.ten if record.linh_vuc else "") or "") +
                    ((record.nganh_hang.ten if record.nganh_hang else "") or "") +
                    ((record.nhan_hang.ten if record.nhan_hang else "") or "")
            )
            if text:
                vec_dict = record._name_to_vector(text)
                record.vector_group = json.dumps(vec_dict)
            else:
                record.vector_group = False

    def get_vector_mdm(self):
        data = self.search([])
        for r in data:
            if r.ten:
                vec_dict = r._name_to_vector(r.ten)
                r.vector = json.dumps(vec_dict)
            else:
                r.vector = False

    def get_vector_group_mdm(self):
        data = self.search([])
        for record in data:
            text = (
                    ((record.chung_loai1.ten if record.chung_loai1 else "") or "") +
                    ((record.chung_loai2.ten if record.chung_loai2 else "") or "") +
                    ((record.linh_vuc.ten if record.linh_vuc else "") or "") +
                    ((record.nganh_hang.ten if record.nganh_hang else "") or "") +
                    ((record.nhan_hang.ten if record.nhan_hang else "") or "")
            )
            if text:
                vec_dict = record._name_to_vector(text)
                record.vector_group = json.dumps(vec_dict)
            else:
                record.vector_group = False

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

    @api.model
    def create(self, vals):
        record = super().create(vals)
        self.create_write_action_data(record)
        self.call_api_insert(record)

        # Nếu không có vector thì bỏ qua
        # if not record.vector:
        #     return record
        #
        # new_vec = json.loads(record.vector)
        # # new_vec_group = json.loads(record.vector_group)
        #
        # logs = []
        # offset = 0
        # limit = 5000
        #
        # while True:
        #     batch = self.sudo().search_read(
        #         [('id', '!=', record.id)],
        #         ['id', 'vector', 'ten', 'vector_group'],
        #         offset=offset,
        #         limit=limit
        #     )
        #
        #     if not batch:
        #         break
        #
        #     for r in batch:
        #         if not r['vector']:
        #             continue
        #
        #         # 🚀 Tối ưu 1: lọc theo độ dài tên trước
        #         if record.ten and r['ten']:
        #             if abs(len(record.ten) - len(r['ten'])) > 5:
        #                 continue
        #
        #         old_vec = json.loads(r['vector'])
        #
        #         score = self._cosine_similarity_dict(new_vec, old_vec)
        #
        #         if score >= 0.8:
        #             logs.append({
        #                 'mdm': record.id,
        #                 'record': r['id'],
        #                 'ten': r['ten'],
        #                 'score': score * 100
        #             })
        #
        #     offset += limit
        #
        # if logs:
        #     self.env['ket.qua.tong.hop'].sudo().create(logs)

        return record

    def create_write_action_data(self, record):
        if not record.vector:
            return record

        new_vec = json.loads(record.vector)
        new_vec_group = json.loads(record.vector_group)

        logs = []
        offset = 0
        limit = 5000

        while True:
            batch = self.sudo().search_read(
                [('id', '!=', record.id)],
                ['id', 'vector', 'ten', 'vector_group'],
                offset=offset,
                limit=limit
            )

            if not batch:
                break

            for r in batch:
                if not r['vector']:
                    continue

                # 🚀 Tối ưu 1: lọc theo độ dài tên trước
                name_match = False
                if record.ten and r['ten']:
                    if record.ten.lower() in r['ten'].lower():
                        name_match = True

                old_vec = json.loads(r['vector'])
                old_vec_group = json.loads(r['vector_group'])

                score = self._cosine_similarity_dict(new_vec, old_vec)
                score_group = self._cosine_similarity_dict(new_vec_group, old_vec_group)

                if (score >= 0.8 or name_match) and (score_group >= 0.5):
                    logs.append({
                        'mdm': record.id,
                        'record': r['id'],
                        'ten': r['ten'],
                        'score': score * 100,
                        'score_group': score_group * 100
                    })

            offset += limit
        self.env['ket.qua.tong.hop'].sudo().search([('mdm', '=', record.id)]).unlink()
        if logs:
            self.env['ket.qua.tong.hop'].sudo().create(logs)

    def action_open_update_popup(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Nhập thêm thông tin',
            'res_model': 'mdm.tong.hop',
            'view_mode': 'form',
            'view_id': self.env.ref('sonha_mdm.view_mdm_tong_hop_update_form').id,
            'res_id': self.id,
            'target': 'new'
        }

    def action_save_popup(self):
        for r in self:
            self.create_write_action_data(r)
        return {'type': 'ir.actions.act_window_close'}

    def action_confirm_data(self):
        for r in self:
            self.create_write_action_data(r)

    def call_api_insert(self, record):
        data = {'ma_chung_loai1': record.chung_loai1.ma or None,
                'ten_chung_loai1': record.chung_loai1.ten or None,
                'ma_chung_loai2': record.chung_loai2.ma or None,
                'ten_chung_loai2': record.chung_loai2.ten or None,
                'ma_linh_vuc': record.linh_vuc.ma or None,
                'ten_linh_vuc': record.linh_vuc.ten or None,
                'ma_nganh_hang': record.nganh_hang.ma or None,
                'ten_nganh_hang': record.nganh_hang.ten or None,
                'ma_nhan_hang': record.nhan_hang.ma or None,
                'ten_nhan_hang': record.nhan_hang.ten or None,
                'ma': record.ma or None,
                'ten': record.ten or None,
                'ma_tg': record.ma_tg or None,
                'ten_ngan': record.ten_ngan or None,
                'dvt': record.dvt or None,
                'ma_dvcs': record.dvcs.company_code or None,
                'ten_dvcs': record.dvcs.name or None,
                'type': 'insert',
                }

        # 👉 convert sang JSON string
        json_str = json.dumps(data, ensure_ascii=False)

        # 🔥 thêm dấu ' 2 bên (theo yêu cầu API của bạn)
        payload = f"'{json_str}'"

        try:
            response = requests.put(
                "https://bhapi.sonha.com.vn/api/mdm_hh",
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
        data = {'ma_chung_loai1': record.chung_loai1.ma or None,
                'ten_chung_loai1': record.chung_loai1.ten or None,
                'ma_chung_loai2': record.chung_loai2.ma or None,
                'ten_chung_loai2': record.chung_loai2.ten or None,
                'ma_linh_vuc': record.linh_vuc.ma or None,
                'ten_linh_vuc': record.linh_vuc.ten or None,
                'ma_nganh_hang': record.nganh_hang.ma or None,
                'ten_nganh_hang': record.nganh_hang.ten or None,
                'ma_nhan_hang': record.nhan_hang.ma or None,
                'ten_nhan_hang': record.nhan_hang.ten or None,
                'ma': record.ma or None,
                'ten': record.ten or None,
                'ma_tg': record.ma_tg or None,
                'ten_ngan': record.ten_ngan or None,
                'dvt': record.dvt or None,
                'ma_dvcs': record.dvcs.company_code or None,
                'ten_dvcs': record.dvcs.name or None,
                'type': 'update',
                }

        # 👉 convert sang JSON string
        json_str = json.dumps(data, ensure_ascii=False)

        # 🔥 thêm dấu ' 2 bên (theo yêu cầu API của bạn)
        payload = f"'{json_str}'"

        try:
            response = requests.put(
                "https://bhapi.sonha.com.vn/api/mdm_hh",
                json=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8'
                },
                timeout=10
            )

            # debug
            print("API hàng hóa:", response.text)

        except Exception as e:
            print("API hàng hóa:", str(e))

    def write(self, vals):
        res = super().write(vals)
        for r in self:
            self.create_write_action_data(r)
            self.call_api_update(r)
        return res

