import os
import json
import logging
import re

import numpy as np
import unicodedata
from numpy.linalg import norm
from openai import OpenAI
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from sentence_transformers import SentenceTransformer

_logger = logging.getLogger(__name__)

# Cache client ở module level để tránh tạo nhiều lần
_OPENAI_CLIENT = None


def preprocess_text(s: str, mapping: dict = None) -> str:
    """Chuẩn hóa text: tách chữ số, ký tự, thay viết tắt"""
    import re
    s = s.strip().lower()
    s = re.sub(r'([a-zA-Z])([0-9])', r'\1 \2', s)
    s = re.sub(r'([0-9])([a-zA-Z])', r'\1 \2', s)
    s = re.sub(r'([^a-z0-9\.])', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()

    if mapping:
        for k, v in mapping.items():
            pattern = r'\b' + re.escape(k.lower()) + r'\b'
            s = re.sub(pattern, v.lower(), s)

    return s


# def tokenize(text):
#     # Tách số và chữ riêng
#     tokens = re.findall(r'[a-z]+\d+|\d+[a-z]+|\d+\.\d+|\d+|[a-z]+', text)
#
#     return tokens

MODEL = SentenceTransformer(
        "nomic-ai/nomic-embed-text-v1.5",
        trust_remote_code=True,
        revision="main"
    )

class HangHoaVatTu(models.Model):
    _name = 'hang.hoa.vat.tu'

    name = fields.Text("Tên")
    vector = fields.Char("Vector")
    data_rel = fields.One2many('data.md', 'vat_tu', string="Dữ liệu")

    # def _get_openai_client(self):
    #     """
    #     Lấy OpenAI client, cache lại. Nên lưu key ở System Parameters (key=openai.api_key)
    #     hoặc dùng biến môi trường OPENAI_API_KEY.
    #     """
    #     global _OPENAI_CLIENT
    #     if _OPENAI_CLIENT is not None:
    #         return _OPENAI_CLIENT
    #
    #     # 1) Thử lấy từ ir.config_parameter
    #     api_key = False
    #     try:
    #         api_key = self.env['ir.config_parameter'].sudo().get_param('openai.api_key')
    #     except Exception:
    #         api_key = None
    #
    #     # 2) Fallback: biến môi trường
    #     if not api_key:
    #         api_key = os.environ.get('OPENAI_API_KEY')
    #
    #     if not api_key:
    #         raise UserError(
    #             _("OpenAI API key not found. Set 'openai.api_key' in System Parameters or set OPENAI_API_KEY env var."))
    #
    #     try:
    #         # Tạo client 1 lần
    #         _OPENAI_CLIENT = OpenAI(api_key=api_key)
    #         return _OPENAI_CLIENT
    #     except Exception as e:
    #         _logger.exception("Cannot initialize OpenAI client: %s", e)
    #         raise UserError(_("Cannot initialize OpenAI client: %s") % e)

    def complete_approval(self):
        for rec in self:
            if rec.name:
                emb = MODEL.encode(rec.name).tolist()
                rec.vector = json.dumps(emb)
                vec_a = np.array(json.loads(rec.vector))
                rec.data_rel.unlink()
                xy_records = self.env['sonha.md'].sudo().search([])
                result_vals = []
                for xy in xy_records:
                    if not xy.vector:
                        continue
                    vec_b = np.array(json.loads(xy.vector))

                    # cosine similarity
                    sim = float(np.dot(vec_a, vec_b) / (norm(vec_a) * norm(vec_b)))
                    sim_percent = round(sim * 100, 2)

                    result_vals.append({
                        "vat_tu": rec.id,
                        "code": xy.code,
                        "name": xy.name,
                        "ti_le": sim_percent,
                    })

                    # Tạo mới dữ liệu trong c.d
                self.env['data.md'].sudo().create(result_vals)

    def complete_vector(self):
        list_record = self.env['sonha.md'].sudo().search([('vector', '=', None)])
        for r in list_record:
            if r.name:
                emb = MODEL.encode(r.name).tolist()
                r.vector = json.dumps(emb)

    # def complete_vector(self):
    #     """Sinh embedding cho toàn bộ sonha.md và lưu lại"""
    #     list_record = self.env['sonha.md'].sudo().search([])
    #     client = self._get_openai_client()
    #
    #     for rec in list_record:
    #         if not rec.name:
    #             continue
    #
    #         # clean_name = normalize_text(rec.name)
    #         # clean_name = set(tokenize(clean_name))
    #         clean_name = {'inox', 'bang', '0201', '2b', '0.58', '0049', 'x3'}
    #
    #         try:
    #             response = client.embeddings.create(
    #                 model="text-embedding-3-large",
    #                 input=clean_name
    #             )
    #             emb = response.data[0].embedding
    #         except Exception as e:
    #             _logger.exception("Embedding failed for record %s: %s", rec.id, e)
    #             continue
    #
    #         if not emb:
    #             _logger.warning("Empty embedding for record %s", rec.id)
    #             continue
    #
    #         rec.vector = json.dumps(emb)
    #
    # def complete_approval(self):
    #     """So sánh self.name với toàn bộ sonha.md đã có vector"""
    #     client = self._get_openai_client()
    #
    #     for rec in self:
    #         if not rec.name:
    #             continue
    #
    #         clean_name = normalize_text(rec.name)
    #         clean_name = ['xb', '0201', '2b', '0.58', '0049', 'x3']
    #
    #         # text = "Inox Băng 0201 2B dày 0.58 0049 X3"
    #         # clean_name_2 = normalize_text(text)
    #         clean_name_2 = ['inox', 'bang', '0201', '2b', 'day', '0.58', '0049', 'x3']
    #
    #         clean_test = {'xb', '0201', '2b', '0.58', '0049', 'x3'}
    #         # clean_name_2 = {'inox', 'bang', '0201', '2b', '0.58', '0049', 'x3'}
    #
    #         try:
    #             response_1 = client.embeddings.create(
    #                 model="text-embedding-3-large",
    #                 input=clean_name
    #             )
    #             emb = response_1.data[0].embedding
    #
    #             response_2 = client.embeddings.create(
    #                 model="text-embedding-3-large",
    #                 input=clean_name_2
    #             )
    #             emb_2 = response_2.data[0].embedding
    #         except Exception as e:
    #             _logger.exception("Embedding failed for rec %s: %s", rec.id, e)
    #             continue
    #
    #         # rec.vector = json.dumps(emb)
    #         vec_a = np.array(emb, dtype=float)
    #         vec_b = np.array(emb_2, dtype=float)
    #
    #         denom = norm(vec_a) * norm(vec_b)
    #         sim = float(np.dot(vec_a, vec_b) / denom) if denom else 0.0
    #         sim_percent = round(sim * 100, 2)
    #
    #         x = 1
    #         z = 2

            # clear dữ liệu cũ
            # rec.data_rel.unlink()
            # result_vals = []
            #
            # xy_records = self.env['sonha.md'].sudo().search([])
            #
            # for xy in xy_records:
            #     if not xy.vector:
            #         continue
            #     try:
            #         vec_b = np.array(json.loads(xy.vector), dtype=float)
            #         denom = norm(vec_a) * norm(vec_b)
            #         sim = float(np.dot(vec_a, vec_b) / denom) if denom else 0.0
            #         sim_percent = round(sim * 100, 2)
            #
            #         result_vals.append({
            #             "vat_tu": rec.id,
            #             "code": xy.code,
            #             "name": xy.name,
            #             "ti_le": sim_percent,
            #         })
            #     except Exception as e:
            #         _logger.exception("Compare failed for rec %s vs %s: %s", rec.id, xy.id, e)
            #         continue
            #
            # if result_vals:
            #     self.env['data.md'].sudo().create(result_vals)

