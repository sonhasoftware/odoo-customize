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

    # --------- Normalize & domain-specific mapping ----------

    def _normalize_text(self, text):
        """
        - remove accents
        - lowercase
        - separate letters and numbers with spaces
        - keep decimals but normalize spacing
        """
        if not text:
            return ""
        # remove accents
        t = unicodedata.normalize("NFKD", text)
        t = "".join([c for c in t if not unicodedata.combining(c)])
        t = t.lower().strip()

        # separate letters/numbers: "XB0201" -> "xb 0201"
        t = re.sub(r'([A-Za-z])([0-9])', r'\1 \2', t)
        t = re.sub(r'([0-9])([A-Za-z])', r'\1 \2', t)

        # replace non-alnum (except dot) with space
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

    # --------- Numeric similarity: compare numeric tokens with tolerance ----------
    def _numeric_similarity(self, s1, s2):
        # find numbers (integers or floats)
        nums1 = re.findall(r'\d+(?:\.\d+)?', s1)
        nums2 = re.findall(r'\d+(?:\.\d+)?', s2)
        if not nums1 and not nums2:
            return 0.0
        if not nums1 or not nums2:
            return 0.0
        # match each number in shorter list to best in longer list
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
            if best_i is not None and best > 0.6:  # threshold to count as match
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

    # --------- hybrid similarity combining multiple signals ----------
    def _hybrid_similarity(self, s1, s2, weights=None, use_semantic=True):
        """
        weights: dict with keys: token_set, partial, seq, numeric, char_ngram, semantic
        returns score in 0..100
        """
        if weights is None:
            weights = {
                'token_set': 0.5,   # rapidfuzz token_set_ratio
                'partial': 0.15,     # rapidfuzz partial_ratio
                'seq': 0.15,         # SequenceMatcher
                'numeric': 0.4,     # numeric matching
                'char_ngram': 0.15,  # char ngram jaccard
                'semantic': 0.15,    # embedding cosine
            }

        # normalize original strings
        t1 = self._normalize_text(s1)
        t2 = self._normalize_text(s2)

        # token-based scores (rapidfuzz returns 0..100)
        try:
            token_set = fuzz.token_set_ratio(t1, t2) / 100.0
            partial = fuzz.partial_ratio(t1, t2) / 100.0
            seq = SequenceMatcher(None, t1, t2).ratio()  # 0..1
        except Exception:
            token_set = partial = seq = 0.0

        # numeric score 0..1
        numeric = self._numeric_similarity(s1, s2)

        # char ngram
        char_ng = self._char_ngram_jaccard(t1, t2, n=3)

        # semantic via embedding (0..1)
        semantic = 0.0
        if use_semantic:
            # try use stored vectors first to save time
            v1 = None; v2 = None
            # We cannot access recs here; we'll just encode on the fly
            try:
                emb1 = MODEL.encode(t1)
                emb2 = MODEL.encode(t2)
                semantic = float(np.dot(emb1, emb2) / (norm(emb1) * norm(emb2)))
                if np.isnan(semantic):
                    semantic = 0.0
            except Exception:
                semantic = 0.0

        # combine weighted
        total = (weights['token_set'] * token_set +
                 weights['partial'] * partial +
                 weights['seq'] * seq +
                 weights['numeric'] * numeric +
                 weights['char_ngram'] * char_ng +
                 weights['semantic'] * semantic)

        # scale to 0..100
        return round(total * 100, 2)

    # --------- Main button (giữ cấu trúc tạo data.md) ----------
    def complete_approval(self):
        for rec in self:
            if not rec.name:
                continue

            if not rec.vector:
                try:
                    v = self._encode_text(rec.name)
                    rec.vector = json.dumps(v)
                except Exception:
                    rec.vector = False

            rec.data_rel.unlink()
            result_vals = []
            sonha_records = self.env['sonha.md'].sudo().search([])

            for xy in sonha_records:
                if not xy.name:
                    continue

                try:
                    sim_percent = self._hybrid_similarity(rec.name, xy.name, use_semantic=True)
                except Exception:
                    sim_percent = 0.0

                if sim_percent > 0:
                    result_vals.append({
                        'vat_tu': rec.id,
                        'code': getattr(xy, 'code', ''),
                        'name': xy.name,
                        'ti_le': sim_percent,
                    })

            result_vals.sort(key=lambda x: x['ti_le'], reverse=True)
            if result_vals:
                self.env['data.md'].sudo().create(result_vals)
