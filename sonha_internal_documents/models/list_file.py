from odoo import api, fields, models, _

import base64


class ListFile(models.Model):
    _name = 'danh.sach.file'
    _rec_name = 'file_name'

    file_name = fields.Char("Tên file")
    file = fields.Binary("Tập tin")
    base64 = fields.Text("Base64", compute="get_base_64")
    parent_id = fields.Many2one("dk.vb.h", string="Cha")

    @api.depends('file')
    def get_base_64(self):
        for r in self:
            if r.file:
                r.base64 = base64.b64decode(r.file)
