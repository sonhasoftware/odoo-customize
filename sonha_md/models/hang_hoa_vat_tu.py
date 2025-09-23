from odoo import models, fields, api
import re
import unicodedata
import json
import numpy as np
from numpy.linalg import norm
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer

# Load model once
MODEL = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


class HangHoaVatTu(models.Model):
    _name = 'hang.hoa.vat.tu'
    _description = 'Hàng Hóa Vật Tư'

    name = fields.Text("Tên")
    vector = fields.Text("Vector")   # Lưu JSON string của embedding
    data_rel = fields.One2many('data.md', 'vat_tu', string="Dữ liệu")

    # --------- Normalize ----------
    def _normalize_text(self, text):
        if not text:
            return ""
        t = unicodedata.normalize("NFKD", text)
        t = "".join([c for c in t if not unicodedata.combining(c)])
        t = t.lower().strip()
        t = re.sub(r'([A-Za-z])([0-9])', r'\1 \2', t)
        t = re.sub(r'([0-9])([A-Za-z])', r'\1 \2', t)
        t = re.sub(r'[^a-z0-9\.]+', ' ', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t

    # --------- Embedding helpers ----------
    def _encode_text(self, text):
        if not text:
            return None
        txt = self._normalize_text(text)
        emb = MODEL.encode(txt)
        return emb.tolist()

    def _cosine_from_vectors(self, v1, v2):
        v1 = np.array(v1); v2 = np.array(v2)
        if v1.shape != v2.shape:
            return 0.0
        denom = (norm(v1) * norm(v2))
        if denom == 0:
            return 0.0
        return float(np.dot(v1, v2) / denom)

    # --------- Numeric similarity ----------
    def _numeric_similarity(self, s1, s2):
        nums1 = re.findall(r'\d+(?:\.\d+)?', s1)
        nums2 = re.findall(r'\d+(?:\.\d+)?', s2)
        if not nums1 and not nums2:
            return 0.0
        if not nums1 or not nums2:
            return 0.0
        matched = 0
        used = set()
        for n1 in nums1:
            try:
                f1 = float(n1)
            except:
                f1 = None
            best = 0.0
            best_i = None
            for i, n2 in enumerate(nums2):
                if i in used:
                    continue
                try:
                    f2 = float(n2)
                except:
                    f2 = None
                if f1 is not None and f2 is not None:
                    if max(abs(f1), abs(f2)) == 0:
                        closeness = 1.0 if f1 == f2 else 0.0
                    else:
                        closeness = 1 - abs(f1 - f2) / max(abs(f1), abs(f2))
                        if closeness < 0:
                            closeness = 0.0
                else:
                    closeness = 1.0 if n1 == n2 else 0.0
                if closeness > best:
                    best = closeness
                    best_i = i
            if best_i is not None and best > 0.6:
                matched += 1
                used.add(best_i)
        total = max(len(nums1), len(nums2))
        return matched / total

    # --------- char n-gram jaccard ----------
    def _char_ngram_jaccard(self, s1, s2, n=3):
        def ngrams(s, n):
            s = re.sub(r'\s+', '', s)
            return {s[i:i+n] for i in range(max(0, len(s)-n+1))}
        a = ngrams(s1, n)
        b = ngrams(s2, n)
        if not a or not b:
            return 0.0
        inter = len(a & b)
        uni = len(a | b)
        return inter / uni if uni > 0 else 0.0

    # --------- hybrid similarity ----------
    def _hybrid_similarity(self, s1, s2, v1=None, v2=None, weights=None, use_semantic=True):
        if weights is None:
            weights = {
                'token_set': 0.5,
                'partial': 0.15,
                'seq': 0.15,
                'numeric': 0.4,
                'char_ngram': 0.15,
                'semantic': 0.15,
            }

        t1 = self._normalize_text(s1)
        t2 = self._normalize_text(s2)

        try:
            token_set = fuzz.token_set_ratio(t1, t2) / 100.0
            partial = fuzz.partial_ratio(t1, t2) / 100.0
            seq = SequenceMatcher(None, t1, t2).ratio()
        except Exception:
            token_set = partial = seq = 0.0

        numeric = self._numeric_similarity(s1, s2)
        char_ng = self._char_ngram_jaccard(t1, t2, n=3)

        semantic = 0.0
        if use_semantic and v1 is not None and v2 is not None:
            try:
                semantic = self._cosine_from_vectors(v1, v2)
            except Exception:
                semantic = 0.0

        total = (weights['token_set'] * token_set +
                 weights['partial'] * partial +
                 weights['seq'] * seq +
                 weights['numeric'] * numeric +
                 weights['char_ngram'] * char_ng +
                 weights['semantic'] * semantic)

        return round(total * 100, 2)

    # --------- Main button ----------
    def complete_approval(self):
        for rec in self:
            if not rec.name:
                continue

            # Sinh vector cho vật tư hiện tại nếu chưa có
            if not rec.vector:
                try:
                    v1 = self._encode_text(rec.name)
                    rec.vector = json.dumps(v1)
                except Exception:
                    rec.vector = False
                    v1 = None
            else:
                v1 = json.loads(rec.vector)

            rec.data_rel.unlink()
            result_vals = []
            sonha_records = self.env['sonha.md'].sudo().search([('vector', '!=', False)])

            for xy in sonha_records:
                if not xy.name:
                    continue
                try:
                    v2 = json.loads(xy.vector)
                except Exception:
                    v2 = None

                try:
                    sim_percent = self._hybrid_similarity(
                        rec.name, xy.name, v1=v1, v2=v2, use_semantic=True
                    )
                except Exception:
                    sim_percent = 0.0

                if sim_percent > 0:
                    result_vals.append({
                        'vat_tu': rec.id,
                        'code': xy.code or '',
                        'name': xy.name,
                        'ti_le': sim_percent,
                    })

            result_vals.sort(key=lambda x: x['ti_le'], reverse=True)
            if result_vals:
                self.env['data.md'].sudo().create(result_vals)

    def complete_vector(self):
        """Sinh vector cho các record chưa có vector"""
        for rec in self.env['sonha.md'].sudo().search([('vector', '=', False)]):
            if rec.name:
                emb = MODEL.encode(rec.name).tolist()
                rec.vector = json.dumps(emb)
