# -*- coding: utf-8 -*-
"""
dynamic_model_field.py
----------------------
Model cấu hình từng field trong dynamic model.
Một dynamic.model có nhiều dynamic.model.field (One2many).
"""

import re
from odoo import api, fields, models
from odoo.exceptions import ValidationError


# Các field type được hỗ trợ
FIELD_TYPE_SELECTION = [
    ('char', 'Char (Văn bản ngắn)'),
    ('text', 'Text (Văn bản dài)'),
    ('integer', 'Integer (Số nguyên)'),
    ('float', 'Float (Số thực)'),
    ('boolean', 'Boolean (Đúng/Sai)'),
    ('date', 'Date (Ngày)'),
    ('datetime', 'Datetime (Ngày giờ)'),
    ('selection', 'Selection (Lựa chọn)'),
    ('many2one', 'Many2one (N→1)'),
    ('one2many', 'One2many (1→N)'),
    ('many2many', 'Many2many (N↔N)'),
    ('binary', 'Binary (File/Ảnh)'),
    ('html', 'Html (Rich Text)'),
    ('monetary', 'Monetary (Tiền tệ)'),
]


class DynamicModelField(models.Model):
    _name = 'dynamic.model.field'
    _description = 'Dynamic Model Field - Định nghĩa từng trường'
    _order = 'sequence asc, id asc'

    # ─────────────────────────────────────────────
    # QUAN HỆ VỀ MODEL CHA
    # ─────────────────────────────────────────────
    dynamic_model_id = fields.Many2one(
        comodel_name='dynamic.model',
        string='Dynamic Model',
        required=True,
        ondelete='cascade',  # Xóa field khi xóa model cha
    )

    # ─────────────────────────────────────────────
    # CẤU HÌNH CƠ BẢN
    # ─────────────────────────────────────────────
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
        help='Thứ tự hiển thị trong form/list view'
    )
    field_name = fields.Char(
        string='Technical Name',
        required=True,
        help='Tên kỹ thuật của field. Không cần thêm x_ (sẽ tự thêm).\nVí dụ: title, price, publish_date'
    )
    field_label = fields.Char(
        string='Label hiển thị',
        required=True,
        help='Tên hiển thị cho người dùng. Ví dụ: Tiêu đề sách, Giá bán'
    )
    field_type = fields.Selection(
        selection=FIELD_TYPE_SELECTION,
        string='Kiểu dữ liệu',
        required=True,
        default='char',
    )

    # ─────────────────────────────────────────────
    # THUỘC TÍNH CHUNG
    # ─────────────────────────────────────────────
    required = fields.Boolean(
        string='Bắt buộc nhập',
        default=False,
    )
    readonly = fields.Boolean(
        string='Chỉ đọc',
        default=False,
    )
    indexed = fields.Boolean(
        string='Đánh chỉ mục (Index)',
        default=False,
        help='Thêm database index để tăng tốc tìm kiếm'
    )
    help_text = fields.Char(
        string='Ghi chú/Tooltip',
        help='Văn bản hiển thị khi hover vào field trong form'
    )
    default_value = fields.Char(
        string='Giá trị mặc định',
        help='Giá trị mặc định khi tạo bản ghi mới (dạng string, sẽ được parse theo type)'
    )

    # ─────────────────────────────────────────────
    # THUỘC TÍNH RIÊNG CHO TỪNG TYPE
    # ─────────────────────────────────────────────

    # Char
    char_size = fields.Integer(
        string='Độ dài tối đa (Char)',
        default=255,
        help='Chỉ áp dụng cho kiểu Char'
    )

    # Selection: lưu dạng "value1:Label1,value2:Label2"
    selection_options = fields.Text(
        string='Danh sách lựa chọn',
        help=(
            'Nhập mỗi lựa chọn một dòng theo format: value|Label\n'
            'Ví dụ:\n'
            'draft|Nháp\n'
            'published|Đã xuất bản\n'
            'archived|Lưu trữ'
        ),
    )

    # Relational fields
    relation = fields.Char(
        string='Model quan hệ',
        help=(
            'Technical name của model đích.\n'
            'Ví dụ: res.partner, product.product, x_book'
        )
    )
    relation_field = fields.Char(
        string='Inverse Field (One2many)',
        help=(
            'Tên Many2one field bên model kia trỏ về model này.\n'
            'Chỉ cần cho kiểu One2many.'
        )
    )
    domain = fields.Char(
        string='Domain lọc',
        help="Domain để lọc records. Ví dụ: [('active', '=', True)]"
    )

    # ─────────────────────────────────────────────
    # COMPUTED: hiển thị tóm tắt
    # ─────────────────────────────────────────────
    field_summary = fields.Char(
        string='Tóm tắt',
        compute='_compute_field_summary',
    )

    @api.depends('field_name', 'field_type', 'required', 'relation')
    def _compute_field_summary(self):
        for rec in self:
            parts = [f'[{rec.field_type}]']
            if rec.required:
                parts.append('*Required*')
            if rec.relation:
                parts.append(f'→ {rec.relation}')
            rec.field_summary = ' '.join(parts)

    # ─────────────────────────────────────────────
    # VISIBILITY HELPERS (dùng trong XML attrs)
    # ─────────────────────────────────────────────
    show_char_options = fields.Boolean(compute='_compute_show_options')
    show_selection_options = fields.Boolean(compute='_compute_show_options')
    show_relation_options = fields.Boolean(compute='_compute_show_options')
    show_one2many_options = fields.Boolean(compute='_compute_show_options')

    @api.depends('field_type')
    def _compute_show_options(self):
        for rec in self:
            rec.show_char_options = rec.field_type == 'char'
            rec.show_selection_options = rec.field_type == 'selection'
            rec.show_relation_options = rec.field_type in ('many2one', 'one2many', 'many2many')
            rec.show_one2many_options = rec.field_type == 'one2many'

    # ─────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────
    @api.constrains('field_name')
    def _check_field_name(self):
        """
        field_name chỉ được chứa chữ thường, số, dấu _.
        Không được bắt đầu bằng số.
        """
        for rec in self:
            # Bỏ x_ prefix để validate phần core name
            name = rec.field_name
            if name.startswith('x_'):
                name = name[2:]

            if not name:
                raise ValidationError('Technical Name không được để trống sau khi bỏ prefix x_!')

            if not re.match(r'^[a-z][a-z0-9_]*$', name):
                raise ValidationError(
                    f'Technical Name "{rec.field_name}" không hợp lệ!\n'
                    f'Chỉ dùng chữ thường, số, dấu _. Phải bắt đầu bằng chữ cái.\n'
                    f'Ví dụ: title, publish_date, author_id'
                )

    @api.constrains('field_type', 'selection_options')
    def _check_selection_options(self):
        """Kiểm tra selection_options có đúng format không"""
        for rec in self:
            if rec.field_type == 'selection' and rec.selection_options:
                lines = [l.strip() for l in rec.selection_options.strip().splitlines() if l.strip()]
                for line in lines:
                    if '|' not in line:
                        raise ValidationError(
                            f'Dòng "{line}" không đúng format!\n'
                            f'Phải là: value|Label\n'
                            f'Ví dụ: draft|Nháp'
                        )

    # ─────────────────────────────────────────────
    # ONCHANGE
    # ─────────────────────────────────────────────
    @api.onchange('field_label')
    def _onchange_field_label_suggest_name(self):
        """Tự động gợi ý field_name từ field_label"""
        if self.field_label and not self.field_name:
            import re
            name = self.field_label.lower()
            # Normalize tiếng Việt
            replace_map = {
                'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
                'ă': 'a', 'ắ': 'a', 'ặ': 'a', 'ằ': 'a', 'ẵ': 'a', 'ẳ': 'a',
                'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
                'đ': 'd',
                'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
                'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
                'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
                'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
                'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
                'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
                'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
                'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
                'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
            }
            for vi, en in replace_map.items():
                name = name.replace(vi, en)
            name = re.sub(r'[^a-z0-9]+', '_', name).strip('_')
            self.field_name = name

    @api.onchange('field_type')
    def _onchange_field_type_clear_options(self):
        """Reset các option không liên quan khi đổi type"""
        if self.field_type not in ('many2one', 'one2many', 'many2many'):
            self.relation = False
            self.relation_field = False
            self.domain = False
        if self.field_type != 'selection':
            self.selection_options = False
        if self.field_type not in ('many2one',):
            # many2one thường là id field
            if self.field_name and self.field_name.endswith('_id') and self.field_type != 'many2one':
                pass  # Giữ nguyên, không reset

    # ─────────────────────────────────────────────
    # HELPER: Parse selection_options thành list tuple
    # ─────────────────────────────────────────────
    def get_selection_list(self):
        """
        Parse selection_options text thành list of (value, label) tuples.
        Dùng bởi dynamic_model._prepare_field_vals()
        """
        self.ensure_one()
        if not self.selection_options:
            return []

        result = []
        for line in self.selection_options.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if '|' in line:
                value, label = line.split('|', 1)
                result.append((value.strip(), label.strip()))

        return str(result)  # ir.model.fields.selection cần string representation