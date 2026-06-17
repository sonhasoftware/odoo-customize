# -*- coding: utf-8 -*-
"""
dynamic_model.py
----------------
Model cấu hình chính: lưu thông tin về model động cần tạo.
Chứa toàn bộ logic generate (ir.model, ir.model.fields, views, menu, action).
"""

import logging
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Mapping từ field_type của ta sang ttype của ir.model.fields
FIELD_TYPE_MAPPING = {
    'char': 'char',
    'text': 'text',
    'integer': 'integer',
    'float': 'float',
    'boolean': 'boolean',
    'date': 'date',
    'datetime': 'datetime',
    'selection': 'selection',
    'many2one': 'many2one',
    'one2many': 'one2many',
    'many2many': 'many2many',
    'binary': 'binary',
    'html': 'html',
    'monetary': 'monetary',
}


class DynamicModel(models.Model):
    _name = 'dynamic.model'
    _description = 'Dynamic Model Builder - Cấu hình Model Động'
    _order = 'name asc'

    # ─────────────────────────────────────────────
    # FIELDS CẤU HÌNH
    # ─────────────────────────────────────────────
    name = fields.Char(
        string='Tên hiển thị',
        required=True,
        help='Tên hiển thị của model, ví dụ: Quản lý sách'
    )
    model_code = fields.Char(
        string='Technical Name',
        required=True,
        help='Technical name, phải bắt đầu bằng x_ (Odoo custom model convention). Ví dụ: x_book'
    )
    description = fields.Text(
        string='Mô tả',
        help='Mô tả ngắn về mục đích của model này'
    )
    field_ids = fields.One2many(
        comodel_name='dynamic.model.field',
        inverse_name='dynamic_model_id',
        string='Danh sách Fields',
    )

    # ─────────────────────────────────────────────
    # TRẠNG THÁI
    # ─────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Nháp'),
            ('generated', 'Đã Generate'),
        ],
        string='Trạng thái',
        default='draft',
        readonly=True,
        copy=False,
    )

    # Lưu references để có thể xóa sau này
    generated_model_id = fields.Many2one(
        comodel_name='ir.model',
        string='IR Model được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    generated_action_id = fields.Many2one(
        comodel_name='ir.actions.act_window',
        string='Action được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    generated_menu_id = fields.Many2one(
        comodel_name='ir.ui.menu',
        string='Menu được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    generated_form_view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='Form View được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    generated_list_view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='List View được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    generated_search_view_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='Search View được tạo',
        readonly=True,
        copy=False,
        ondelete='set null',
    )

    # ─────────────────────────────────────────────
    # COMPUTED / THỐNG KÊ
    # ─────────────────────────────────────────────
    field_count = fields.Integer(
        string='Số lượng fields',
        compute='_compute_field_count',
    )

    @api.depends('field_ids')
    def _compute_field_count(self):
        for rec in self:
            rec.field_count = len(rec.field_ids)

    # ─────────────────────────────────────────────
    # VALIDATION
    # ─────────────────────────────────────────────
    @api.constrains('model_code')
    def _check_model_code(self):
        """
        Odoo convention: custom model phải bắt đầu bằng x_
        Technical name chỉ dùng ký tự a-z, 0-9, dấu _
        """
        for rec in self:
            if not rec.model_code.startswith('x_'):
                raise ValidationError(
                    f'Technical name "{rec.model_code}" phải bắt đầu bằng "x_".\n'
                    f'Ví dụ: x_book, x_customer_data'
                )
            import re
            if not re.match(r'^[a-z][a-z0-9_]*$', rec.model_code):
                raise ValidationError(
                    f'Technical name "{rec.model_code}" chỉ được chứa chữ thường, số và dấu gạch dưới.'
                )

    @api.constrains('field_ids')
    def _check_field_names_unique(self):
        """Kiểm tra field_name không bị trùng trong cùng một model"""
        for rec in self:
            field_names = rec.field_ids.mapped('field_name')
            if len(field_names) != len(set(field_names)):
                duplicates = [n for n in set(field_names) if field_names.count(n) > 1]
                raise ValidationError(
                    f'Có field bị trùng tên trong model "{rec.name}": {", ".join(duplicates)}'
                )

    # ─────────────────────────────────────────────
    # ONCHANGE HELPERS
    # ─────────────────────────────────────────────
    @api.onchange('name')
    def _onchange_name_suggest_code(self):
        """Tự động gợi ý model_code khi nhập name"""
        if self.name and not self.model_code:
            import re
            # Chuyển "Quản lý sách" → "x_quan_ly_sach"
            code = self.name.lower()
            # Normalize unicode tiếng Việt đơn giản
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
                code = code.replace(vi, en)
            code = re.sub(r'[^a-z0-9]+', '_', code).strip('_')
            self.model_code = f'x_{code}'

    # ─────────────────────────────────────────────
    # GENERATE LOGIC - CỐT LÕI CỦA MODULE
    # ─────────────────────────────────────────────
    def action_generate_module(self):
        """
        Entry point: Generate toàn bộ model, views, menu, action.
        Gọi lần lượt các hàm private bên dưới.
        """
        self.ensure_one()

        if self.state == 'generated':
            raise UserError(
                f'Model "{self.name}" đã được generate rồi!\n'
                f'Hãy dùng nút "Update Model" để cập nhật, '
                f'hoặc "Xóa Model" để xóa trước khi tạo lại.'
            )

        if not self.field_ids:
            raise UserError(
                'Chưa có field nào! Vui lòng thêm ít nhất 1 field trước khi generate.'
            )

        self._validate_before_generate()

        try:
            # Bước 1: Tạo ir.model + ir.model.fields
            ir_model = self._generate_ir_model()
            self._ensure_model_access(ir_model)

            # Bước 2: Tạo Views (form, list, search)
            form_view = self._generate_form_view()
            list_view = self._generate_list_view()
            search_view = self._generate_search_view()

            # Bước 3: Tạo Action + Menu
            action = self._generate_action(form_view, list_view, search_view)
            menu = self._generate_menu(action)

            # Bước 4: Lưu references và chuyển state
            self.write({
                'state': 'generated',
                'generated_model_id': ir_model.id,
                'generated_action_id': action.id,
                'generated_menu_id': menu.id,
                'generated_form_view_id': form_view.id,
                'generated_list_view_id': list_view.id,
                'generated_search_view_id': search_view.id,
            })

            _logger.info('✅ Generated dynamic model: %s (%s)', self.name, self.model_code)

        except Exception as e:
            # Rollback sẽ tự xảy ra do transaction, nhưng log lại lỗi rõ ràng
            _logger.exception('❌ Error generating model %s: %s', self.model_code, str(e))
            raise UserError(f'Lỗi khi generate model:\n{str(e)}')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Generate thành công!',
                'message': (
                    f'Model "{self.name}" đã được tạo thành công!\n'
                    f'Menu mới đã xuất hiện trong Dynamic Modules.'
                ),
                'type': 'success',
                'sticky': True,
            }
        }

    def _validate_before_generate(self):
        """Kiểm tra các điều kiện trước khi generate"""
        # Kiểm tra model_code chưa tồn tại trong ir.model
        existing = self.env['ir.model'].sudo().search([
            ('model', '=', self.model_code)
        ])
        if existing:
            raise UserError(
                f'Model với technical name "{self.model_code}" đã tồn tại trong hệ thống!\n'
                f'Hãy đổi Technical Name sang tên khác.'
            )

        # Kiểm tra các field many2one có relation hợp lệ
        for field in self.field_ids:
            if field.field_type in ('many2one', 'one2many', 'many2many'):
                if not field.relation:
                    raise UserError(
                        f'Field "{field.field_label}" (type: {field.field_type}) '
                        f'bắt buộc phải có Relation Model!'
                    )
                # Kiểm tra relation model có tồn tại không
                target_model = self.env['ir.model'].sudo().search([
                    ('model', '=', field.relation)
                ], limit=1)
                if not target_model:
                    raise UserError(
                        f'Relation model "{field.relation}" của field '
                        f'"{field.field_label}" không tồn tại trong hệ thống!\n'
                        f'Ví dụ hợp lệ: res.partner, product.product'
                    )

    def _generate_ir_model(self):
        """
        Tạo ir.model (model chính) và ir.model.fields (các trường).
        Odoo sẽ tự động tạo table trong database khi ir.model được tạo.
        """
        IrModel = self.env['ir.model'].sudo()
        IrModelFields = self.env['ir.model.fields'].sudo()

        # Tạo model chính
        ir_model = IrModel.create({
            'name': self.name,
            'model': self.model_code,
            'state': 'manual',  # 'manual' = custom model do user tạo
            'transient': False,
        })

        _logger.info('Created ir.model: %s', self.model_code)

        # Tạo từng field
        for field in self.field_ids:
            field_vals = self._prepare_field_vals(ir_model, field)
            IrModelFields.create(field_vals)
            _logger.info('  → Created field: %s (%s)', field.field_name, field.field_type)

        return ir_model

    def _ensure_model_access(self, ir_model):
        """Đảm bảo model động có access cho người dùng nội bộ."""
        IrModelAccess = self.env['ir.model.access'].sudo()
        group_user = self.env.ref('base.group_user')

        existing_access = IrModelAccess.search([
            ('model_id', '=', ir_model.id),
            ('group_id', '=', group_user.id),
        ], limit=1)
        if existing_access:
            return existing_access

        return IrModelAccess.create({
            'name': f'access_{ir_model.model}_user',
            'model_id': ir_model.id,
            'group_id': group_user.id,
            'perm_read': True,
            'perm_write': True,
            'perm_create': True,
            'perm_unlink': True,
        })

    def _prepare_field_vals(self, ir_model, field):
        """
        Chuẩn bị values dict cho ir.model.fields.create()
        Xử lý đặc thù cho từng loại field.
        """
        # Đảm bảo field_name có prefix x_ (Odoo custom fields convention)
        technical_name = field.field_name
        if not technical_name.startswith('x_'):
            technical_name = f'x_{technical_name}'

        ttype = FIELD_TYPE_MAPPING.get(field.field_type, 'char')

        vals = {
            'name': technical_name,
            'field_description': field.field_label,
            'model_id': ir_model.id,
            'ttype': ttype,
            'state': 'manual',
            'required': field.required,
            'readonly': field.readonly,
            'index': field.indexed,
            'copied': True,
        }

        # Xử lý đặc thù theo type
        if field.field_type == 'char':
            vals['size'] = field.char_size or 255

        elif field.field_type == 'selection':
            # selection_ids phải là list of (value, label) tuples dạng string
            if not field.selection_options:
                raise UserError(
                    f'Field "{field.field_label}" type Selection phải có danh sách lựa chọn!'
                )
            vals['selection'] = field.selection_options

        elif field.field_type == 'many2one':
            vals['relation'] = field.relation
            if field.domain:
                vals['domain'] = field.domain

        elif field.field_type == 'one2many':
            vals['relation'] = field.relation
            # one2many cần inverse_name (Many2one field bên kia trỏ về model này)
            if not field.relation_field:
                raise UserError(
                    f'Field "{field.field_label}" (One2many) cần có Inverse Field Name!'
                )
            vals['relation_field'] = field.relation_field

        elif field.field_type == 'many2many':
            vals['relation'] = field.relation

        return vals

    def _generate_form_view(self):
        """Tạo Form View XML cho model động"""
        # Build danh sách field elements cho form view
        field_xml_lines = []
        for field in self.field_ids:
            technical_name = field.field_name
            if not technical_name.startswith('x_'):
                technical_name = f'x_{technical_name}'

            if field.field_type == 'text' or field.field_type == 'html':
                field_xml_lines.append(
                    f'                    <field name="{technical_name}" '
                    f'string="{field.field_label}" colspan="2"/>'
                )
            elif field.field_type == 'boolean':
                field_xml_lines.append(
                    f'                    <field name="{technical_name}" '
                    f'string="{field.field_label}" widget="boolean_toggle"/>'
                )
            else:
                field_xml_lines.append(
                    f'                    <field name="{technical_name}" '
                    f'string="{field.field_label}"/>'
                )

        fields_xml = '\n'.join(field_xml_lines)
        view_name = f'{self.model_code}.form.view'

        arch = f"""<form string="{self.name}">
                <sheet>
                    <div class="oe_title">
                        <h1>
                            <field name="display_name"/>
                        </h1>
                    </div>
                    <group>
                        <group string="Thông tin chính">
{fields_xml}
                        </group>
                    </group>
                </sheet>
            </form>"""

        return self.env['ir.ui.view'].sudo().create({
            'name': view_name,
            'model': self.model_code,
            'type': 'form',
            'arch': arch,
            'priority': 16,
        })

    def _generate_list_view(self):
        """Tạo Tree View XML"""
        field_xml_lines = []
        for field in self.field_ids:
            technical_name = field.field_name
            if not technical_name.startswith('x_'):
                technical_name = f'x_{technical_name}'

            # Bỏ qua text, html, one2many trong list view (không phù hợp)
            if field.field_type in ('text', 'html', 'one2many', 'many2many', 'binary'):
                continue

            field_xml_lines.append(
                f'                <field name="{technical_name}" string="{field.field_label}"/>'
            )

        fields_xml = '\n'.join(field_xml_lines)
        view_name = f'{self.model_code}.tree.view'

        arch = f"""<tree string="{self.name}">
{fields_xml}
            </tree>"""

        return self.env['ir.ui.view'].sudo().create({
            'name': view_name,
            'model': self.model_code,
            'type': 'tree',
            'arch': arch,
            'priority': 16,
        })

    def _generate_search_view(self):
        """Tạo Search View - tự động thêm filter cho các Char fields"""
        search_field_lines = []
        for field in self.field_ids:
            technical_name = field.field_name
            if not technical_name.startswith('x_'):
                technical_name = f'x_{technical_name}'

            # Chỉ char và text mới có thể search full-text
            if field.field_type in ('char', 'text', 'many2one'):
                search_field_lines.append(
                    f'                <field name="{technical_name}" string="{field.field_label}"/>'
                )

        fields_xml = '\n'.join(search_field_lines)
        view_name = f'{self.model_code}.search.view'

        arch = f"""<search string="Tìm kiếm {self.name}">
{fields_xml}
                <separator/>
                <group expand="0" string="Group By">
                </group>
            </search>"""

        return self.env['ir.ui.view'].sudo().create({
            'name': view_name,
            'model': self.model_code,
            'type': 'search',
            'arch': arch,
            'priority': 16,
        })

    def _generate_action(self, form_view, list_view, search_view):
        """Tạo ir.actions.act_window để mở model"""
        return self.env['ir.actions.act_window'].sudo().create({
            'name': self.name,
            'res_model': self.model_code,
            'type': 'ir.actions.act_window',
            'view_mode': 'tree,form',
            'views': [
                (list_view.id, 'tree'),
                (form_view.id, 'form'),
            ],
            'search_view_id': search_view.id,
            'target': 'current',
            'help': f"""
                <p class="o_view_nocontent_smiling_face">
                    Chưa có bản ghi nào!
                </p>
                <p>
                    Nhấn "Tạo mới" để thêm bản ghi đầu tiên vào {self.name}.
                </p>
            """,
        })

    def _generate_menu(self, action):
        """
        Tạo menu item nằm dưới parent menu "Dynamic Modules".
        Parent menu được tìm hoặc tạo tự động.
        """
        IrUiMenu = self.env['ir.ui.menu'].sudo()

        # Tìm parent menu "Dynamic Modules" (được tạo trong views/menu_views.xml)
        parent_menu = IrUiMenu.search([
            ('name', '=', 'Dynamic Modules'),
            ('parent_id', '=', False),  # top-level menu
        ], limit=1)

        if not parent_menu:
            # Fallback: tạo parent menu nếu chưa tồn tại
            parent_menu = IrUiMenu.create({
                'name': 'Dynamic Modules',
                'sequence': 100,
                'web_icon': 'base,static/description/icon.png',
            })

        # Tạo submenu cho model này
        child_menu = IrUiMenu.create({
            'name': self.name,
            'parent_id': parent_menu.id,
            'action': f'ir.actions.act_window,{action.id}',
            'sequence': 10,
        })

        return child_menu

    # ─────────────────────────────────────────────
    # UPDATE MODEL (BONUS)
    # ─────────────────────────────────────────────
    def action_update_model(self):
        """
        Cập nhật views và fields khi user thay đổi cấu hình.
        Chỉ update views + thêm field mới (không xóa field đã có để bảo toàn data).
        """
        self.ensure_one()

        if self.state != 'generated':
            raise UserError('Model chưa được generate, hãy dùng "Generate Module" trước.')

        ir_model = self.generated_model_id
        if not ir_model:
            raise UserError('Không tìm thấy ir.model liên kết. Dữ liệu có thể đã bị xóa thủ công.')

        IrModelFields = self.env['ir.model.fields'].sudo()

        # Lấy danh sách field đã có trong ir.model
        existing_field_names = set(
            IrModelFields.search([
                ('model_id', '=', ir_model.id),
                ('state', '=', 'manual'),
            ]).mapped('name')
        )

        # Thêm các field mới (chưa tồn tại)
        new_fields_added = 0
        for field in self.field_ids:
            technical_name = field.field_name
            if not technical_name.startswith('x_'):
                technical_name = f'x_{technical_name}'

            if technical_name not in existing_field_names:
                field_vals = self._prepare_field_vals(ir_model, field)
                IrModelFields.create(field_vals)
                new_fields_added += 1
                _logger.info('Update: added new field %s to %s', technical_name, self.model_code)

        # Regenerate tất cả views
        self._regenerate_views()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Cập nhật thành công!',
                'message': f'Đã thêm {new_fields_added} field mới và cập nhật views.',
                'type': 'success',
            }
        }

    def _regenerate_views(self):
        """Xóa views cũ và tạo lại views mới"""
        # Xóa views cũ
        for view in [
            self.generated_form_view_id,
            self.generated_list_view_id,
            self.generated_search_view_id,
        ]:
            if view:
                view.sudo().unlink()

        # Tạo views mới
        form_view = self._generate_form_view()
        list_view = self._generate_list_view()
        search_view = self._generate_search_view()

        # Cập nhật action với views mới
        if self.generated_action_id:
            self.generated_action_id.sudo().write({
                'views': [
                    (list_view.id, 'tree'),
                    (form_view.id, 'form'),
                ],
                'search_view_id': search_view.id,
            })

        self.write({
            'generated_form_view_id': form_view.id,
            'generated_list_view_id': list_view.id,
            'generated_search_view_id': search_view.id,
        })

    # ─────────────────────────────────────────────
    # DELETE MODEL (BONUS)
    # ─────────────────────────────────────────────
    def action_delete_generated_model(self):
        """
        Xóa toàn bộ artifacts đã generate: menu, action, views, ir.model.
        CẢNH BÁO: Sẽ xóa tất cả dữ liệu trong model động này!
        """
        self.ensure_one()

        if self.state != 'generated':
            raise UserError('Không có gì để xóa - model chưa được generate.')

        # Mở wizard xác nhận trước khi xóa
        return {
            'type': 'ir.actions.act_window',
            'name': 'Xác nhận xóa Model',
            'res_model': 'dynamic.model.delete.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_dynamic_model_id': self.id},
        }

    def _do_delete_generated_model(self):
        """
        Thực sự xóa tất cả artifacts.
        Được gọi từ wizard sau khi user xác nhận.
        """
        self.ensure_one()
        errors = []

        # Thứ tự xóa: menu → action → views → ir.model
        # (xóa ir.model cuối cùng vì nó sẽ drop table)

        if self.generated_menu_id:
            try:
                self.generated_menu_id.sudo().unlink()
            except Exception as e:
                errors.append(f'Menu: {e}')

        if self.generated_action_id:
            try:
                self.generated_action_id.sudo().unlink()
            except Exception as e:
                errors.append(f'Action: {e}')

        for view_field in ['generated_form_view_id', 'generated_list_view_id', 'generated_search_view_id']:
            view = getattr(self, view_field)
            if view:
                try:
                    view.sudo().unlink()
                except Exception as e:
                    errors.append(f'View: {e}')

        if self.generated_model_id:
            try:
                self.generated_model_id.sudo().unlink()
            except Exception as e:
                errors.append(f'ir.model: {e}')

        if errors:
            raise UserError(
                f'Một số artifacts không thể xóa:\n' + '\n'.join(errors)
            )

        # Reset về trạng thái draft
        self.write({
            'state': 'draft',
            'generated_model_id': False,
            'generated_action_id': False,
            'generated_menu_id': False,
            'generated_form_view_id': False,
            'generated_list_view_id': False,
            'generated_search_view_id': False,
        })

        _logger.info('🗑️ Deleted all artifacts for dynamic model: %s', self.name)

    # ─────────────────────────────────────────────
    # PREVIEW (BONUS)
    # ─────────────────────────────────────────────
    def action_preview(self):
        """Mở wizard preview trước khi generate"""
        self.ensure_one()
        wizard = self.env['dynamic.model.preview.wizard'].create({
            'dynamic_model_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': f'Preview: {self.name}',
            'res_model': 'dynamic.model.preview.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
        }

    # ─────────────────────────────────────────────
    # OPEN GENERATED MODEL
    # ─────────────────────────────────────────────
    def action_open_generated_model(self):
        """Mở model đã generate để xem dữ liệu"""
        self.ensure_one()
        if self.state != 'generated' or not self.generated_action_id:
            raise UserError('Model chưa được generate hoặc action không tồn tại.')

        ir_model = self.generated_model_id
        if not ir_model:
            ir_model = self.env['ir.model'].sudo().search(
                [('model', '=', self.model_code)], limit=1
            )
        if ir_model:
            self._ensure_model_access(ir_model)

        return {
            'type': 'ir.actions.act_window',
            'name': self.name,
            'res_model': self.model_code,
            'view_mode': 'tree,form',
            'target': 'current',
        }