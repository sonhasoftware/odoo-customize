# -*- coding: utf-8 -*-
"""
delete_wizard.py
----------------
Wizard xác nhận xóa model động.
Hiển thị cảnh báo và yêu cầu user gõ lại tên model để xác nhận.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class DynamicModelDeleteWizard(models.TransientModel):
    _name = 'dynamic.model.delete.wizard'
    _description = 'Wizard xác nhận xóa Dynamic Model'

    dynamic_model_id = fields.Many2one(
        comodel_name='dynamic.model',
        string='Dynamic Model',
        required=True,
    )
    model_name = fields.Char(
        related='dynamic_model_id.name',
        string='Tên Model',
        readonly=True,
    )
    confirm_name = fields.Char(
        string='Gõ lại tên model để xác nhận',
        required=True,
        help='Nhập chính xác tên model để xác nhận xóa'
    )
    record_count = fields.Integer(
        string='Số bản ghi hiện có',
        compute='_compute_record_count',
    )
    warning_message = fields.Html(
        string='Cảnh báo',
        compute='_compute_warning_message',
    )

    @api.depends('dynamic_model_id')
    def _compute_record_count(self):
        for rec in self:
            if rec.dynamic_model_id and rec.dynamic_model_id.model_code:
                try:
                    count = self.env[rec.dynamic_model_id.model_code].sudo().search_count([])
                    rec.record_count = count
                except Exception:
                    rec.record_count = 0
            else:
                rec.record_count = 0

    @api.depends('record_count', 'dynamic_model_id')
    def _compute_warning_message(self):
        for rec in self:
            model = rec.dynamic_model_id
            if model:
                rec.warning_message = f"""
                    <div class="alert alert-danger">
                        <strong>⚠️ CẢNH BÁO: Hành động này KHÔNG THỂ HOÀN TÁC!</strong>
                        <ul>
                            <li>Model <strong>{model.name}</strong> ({model.model_code}) sẽ bị xóa hoàn toàn</li>
                            <li>Tất cả <strong>{rec.record_count} bản ghi</strong> trong model này sẽ bị xóa</li>
                            <li>Views, Menu, Action liên quan sẽ bị xóa</li>
                        </ul>
                        <p>Hãy gõ chính xác tên model: <strong>{model.name}</strong></p>
                    </div>
                """
            else:
                rec.warning_message = ''

    def action_confirm_delete(self):
        """Thực hiện xóa sau khi user xác nhận"""
        self.ensure_one()

        if self.confirm_name != self.dynamic_model_id.name:
            raise UserError(
                f'Tên xác nhận không khớp!\n'
                f'Vui lòng gõ chính xác: "{self.dynamic_model_id.name}"'
            )

        # Gọi hàm xóa thật sự
        self.dynamic_model_id._do_delete_generated_model()

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🗑️ Đã xóa thành công',
                'message': f'Model "{self.model_name}" và toàn bộ dữ liệu đã được xóa.',
                'type': 'warning',
            }
        }