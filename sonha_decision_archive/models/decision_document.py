# -*- coding: utf-8 -*-

import base64
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


MAX_FILE_BYTES = 50 * 1024 * 1024


class DecisionDocument(models.Model):
    _name = 'decision.document'
    _description = 'Quyết định và tài liệu công ty'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'issue_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='Tên quyết định / tài liệu', required=True, index=True, tracking=True)
    reference = fields.Char(string='Số / Ký hiệu', required=True, index=True, tracking=True)
    document_type = fields.Selection(
        [
            ('decision', 'Quyết định'),
            ('policy', 'Quy định / Chính sách'),
            ('procedure', 'Quy trình / Hướng dẫn'),
            ('notice', 'Thông báo'),
            ('other', 'Tài liệu khác'),
        ],
        string='Loại tài liệu',
        required=True,
        default='decision',
        index=True,
        tracking=True,
    )
    category_id = fields.Many2one(
        'decision.document.category',
        string='Đầu mục tài liệu',
        required=True,
        index=True,
        ondelete='restrict',
        tracking=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban',
        index=True,
        ondelete='set null',
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Nhân viên liên quan',
        index=True,
        ondelete='set null',
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    issue_date = fields.Date(
        string='Ngày ban hành',
        required=True,
        default=fields.Date.context_today,
        index=True,
        tracking=True,
    )
    effective_date = fields.Date(string='Ngày hiệu lực', index=True, tracking=True)
    expiry_date = fields.Date(string='Ngày hết hiệu lực', index=True, tracking=True)
    signer = fields.Char(string='Người ký / Chức danh', index=True)
    keywords = fields.Char(
        string='Từ khóa tìm kiếm',
        index=True,
        help='Các từ khóa cách nhau bằng dấu phẩy, ví dụ: nhân sự, bổ nhiệm, điều chuyển.',
    )
    summary = fields.Text(string='Tóm tắt nội dung')
    file_data = fields.Binary(string='File quyết định', attachment=True)
    file_name = fields.Char(string='Tên file')
    external_url = fields.Char(
        string='Đường dẫn file bên ngoài',
        help='Đường dẫn HTTP/HTTPS tới SharePoint, Google Drive hoặc kho tài liệu nội bộ.',
    )
    file_url = fields.Char(string='Đường dẫn mở file', compute='_compute_file_info')
    has_file = fields.Boolean(compute='_compute_file_info')
    state = fields.Selection(
        [
            ('draft', 'Bản nháp'),
            ('published', 'Đã công bố'),
            ('archived', 'Lưu trữ'),
        ],
        string='Trạng thái',
        required=True,
        default='draft',
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'decision_reference_company_unique',
            'unique(reference, company_id)',
            'Số / ký hiệu quyết định phải là duy nhất trong cùng công ty.',
        ),
    ]

    @api.depends('file_data', 'file_name', 'external_url')
    def _compute_file_info(self):
        for document in self:
            if document.file_data and document.id:
                filename = quote(document.file_name or 'tai_lieu', safe='')
                document.file_url = (
                    f'/web/content/{document._name}/{document.id}/file_data/{filename}?download=false'
                )
                document.has_file = True
            elif document.external_url:
                document.file_url = document.external_url
                document.has_file = True
            else:
                document.file_url = False
                document.has_file = False

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_id = self.employee_id.department_id

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.category_id:
            self.company_id = self.category_id.company_id
            if self.category_id.department_id and not self.department_id:
                self.department_id = self.category_id.department_id

    @api.constrains('effective_date', 'expiry_date')
    def _check_date_range(self):
        for document in self:
            if document.effective_date and document.expiry_date and document.expiry_date < document.effective_date:
                raise ValidationError(_('Ngày hết hiệu lực không được trước ngày hiệu lực.'))

    @api.constrains('file_data')
    def _check_file_size(self):
        for document in self.filtered('file_data'):
            try:
                file_size = len(base64.b64decode(document.file_data))
            except Exception as error:
                raise ValidationError(_('File tải lên không hợp lệ.')) from error
            if file_size > MAX_FILE_BYTES:
                raise ValidationError(_('Dung lượng file không được vượt quá 50 MB.'))

    @api.constrains('external_url')
    def _check_external_url(self):
        for document in self.filtered('external_url'):
            if not document.external_url.lower().startswith(('http://', 'https://')):
                raise ValidationError(_('Đường dẫn bên ngoài phải bắt đầu bằng http:// hoặc https://.'))

    def action_publish(self):
        for document in self:
            if not document.file_data and not document.external_url:
                raise UserError(_('Vui lòng tải file hoặc nhập đường dẫn file trước khi công bố.'))
        self.write({'state': 'published'})

    def action_archive_document(self):
        self.write({'state': 'archived'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_open_file(self):
        self.ensure_one()
        if not self.file_url:
            raise UserError(_('Tài liệu này chưa có file hoặc đường dẫn.'))
        return {
            'type': 'ir.actions.act_url',
            'url': self.file_url,
            'target': 'new',
        }

