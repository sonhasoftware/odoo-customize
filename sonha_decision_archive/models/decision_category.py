# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class DecisionDocumentCategory(models.Model):
    _name = 'decision.document.category'
    _description = 'Danh mục quyết định và tài liệu'
    _order = 'complete_name, id'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'

    name = fields.Char(string='Tên danh mục', required=True, index=True)
    code = fields.Char(string='Mã danh mục', index=True)
    complete_name = fields.Char(
        string='Đầu mục đầy đủ',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
        index=True,
    )
    parent_id = fields.Many2one(
        'decision.document.category',
        string='Danh mục cha',
        index=True,
        ondelete='restrict',
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'decision.document.category',
        'parent_id',
        string='Danh mục con',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Phòng ban phụ trách',
        index=True,
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Công ty',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    description = fields.Text(string='Mô tả')
    active = fields.Boolean(default=True)
    document_ids = fields.One2many(
        'decision.document',
        'category_id',
        string='Tài liệu',
    )
    document_count = fields.Integer(
        string='Số tài liệu',
        compute='_compute_document_count',
    )

    _sql_constraints = [
        (
            'category_code_company_unique',
            'unique(code, company_id)',
            'Mã danh mục phải là duy nhất trong cùng công ty.',
        ),
    ]

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = f'{category.parent_id.complete_name} / {category.name}'
            else:
                category.complete_name = category.name

    def _compute_document_count(self):
        grouped = self.env['decision.document'].read_group(
            [('category_id', 'in', self.ids)],
            ['category_id'],
            ['category_id'],
        )
        counts = {item['category_id'][0]: item['category_id_count'] for item in grouped}
        for category in self:
            category.document_count = counts.get(category.id, 0)

    @api.constrains('parent_id')
    def _check_parent_id(self):
        if not self._check_recursion():
            raise ValidationError('Danh mục cha và danh mục con đang tạo thành vòng lặp.')

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Tài liệu: {self.complete_name}',
            'res_model': 'decision.document',
            'view_mode': 'tree,form',
            'domain': [('category_id', 'child_of', self.id)],
            'context': {'default_category_id': self.id},
        }

