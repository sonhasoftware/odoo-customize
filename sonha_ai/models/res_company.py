# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError
import os

class ResCompany(models.Model):
    _inherit = 'res.company'

    sonha_ai_knowledge_attachment_ids = fields.Many2many(
        'ir.attachment',
        'sonha_ai_knowledge_attachment_rel',
        'company_id',
        'attachment_id',
        string='AI Knowledge Base Files'
    )

    @api.constrains('sonha_ai_knowledge_attachment_ids')
    def _check_sonha_ai_knowledge_attachments(self):
        allowed_extensions = ['.pdf', '.docx', '.xlsx', '.xls', '.pptx', '.ppt', '.csv', '.json', '.xml', '.txt']
        max_size = 20 * 1024 * 1024  # 20MB
        for company in self:
            for att in company.sonha_ai_knowledge_attachment_ids:
                if att.file_size and att.file_size > max_size:
                    raise ValidationError(f"File '{att.name}' vượt quá giới hạn 20MB.")
                if att.name:
                    ext = os.path.splitext(att.name.lower())[1]
                    if ext not in allowed_extensions:
                        raise ValidationError(f"Định dạng file '{ext}' không được hỗ trợ. Vui lòng tải lên PDF, DOCX, Excel, PPTX, CSV, JSON, hoặc XML.")
