from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpExportDocument(models.Model):
    _name = 'exp.export.document'

    code = fields.Char(string="Mã", store=True)
    type = fields.Char(string="Loại", store=True)
    name = fields.Char(string="Tên", store=True)
    file = fields.Binary(string="File mẫu", store=True)
    file_name = fields.Char(string="Tên file", store=True)
    note = fields.Char(string="Ghi chú", store=True)


class DetailDocument(models.TransientModel):
    _name = 'detail.document'

    document = fields.Many2one('exp.export.document', string="Tên tài liệu", store=True)
    document_file = fields.Binary(string="File mẫu", store=True)
    file_name = fields.Char(string="Tên file", store=True)
    radio_tick = fields.Boolean(string="Active", store=True)
    export_id = fields.Many2one('popup.export.document', store=True)

    @api.onchange('radio_tick')
    def onchange_radio_tick(self):
        for rec in self:
            if rec.radio_tick:
                others = rec.export_id.documents.filtered(lambda l: l.radio_tick and l != rec)
                if others:
                    raise ValidationError("Chỉ được chọn 1 dòng")


