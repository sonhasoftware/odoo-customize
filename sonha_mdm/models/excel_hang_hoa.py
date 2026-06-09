from odoo import api, fields, models
import unicodedata
import re
import json
from collections import Counter
import math
from odoo.exceptions import ValidationError
import requests


class ExcelHangHoa(models.Model):
    _name = 'excel.hang.hoa'

    ma = fields.Char("Mã", index=True, store=True)
    ten = fields.Char("Tên", index=True, store=True)
    vector = fields.Text("Vector", compute="_compute_vector", store=True)
    so_sanh = fields.One2many('excel.hang.hoa.line', 'key', string="Chi tiết")

    @api.depends('ten')
    def _compute_vector(self):
        for record in self:
            if record.ten:
                vec_dict = record._name_to_vector(record.ten)
                record.vector = json.dumps(vec_dict)
            else:
                record.vector = False

    def action_confirm_data(self):
        for r in self:
            self.create_write_action_data(r)

    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.create_write_action_data(record)
        return records

    def create_write_action_data(self, record):
        if not record.vector:
            return record

        new_vec = json.loads(record.vector)

        logs = []
        offset = 0
        limit = 5000

        while True:
            batch = self.env['mdm.tong.hop'].sudo().search_read(
                [(1, '=', 1)],
                ['id', 'vector', 'ten', 'ma'],
                offset=offset,
                limit=limit
            )

            if not batch:
                break

            for r in batch:
                if not r['vector']:
                    continue

                old_vec = json.loads(r['vector'])

                score = self._cosine_similarity_dict(new_vec, old_vec)

                if score >= 0.8:
                    logs.append({
                        'key': record.id,
                        'ma': record.ma,
                        'ten': record.ten,
                        'ma_mdm': r['ma'],
                        'ten_mdm': r['ten'],
                        'percent': score * 100,
                    })

            offset += limit
        self.env['excel.hang.hoa.line'].sudo().search([('key', '=', record.id)]).unlink()
        if logs:
            self.env['excel.hang.hoa.line'].sudo().create(logs)
