# -*- coding: utf-8 -*-
"""
preview_wizard.py
-----------------
Wizard xem trước cấu trúc sẽ được generate.
Hiển thị: danh sách fields, XML arch mẫu của form/list view.
"""

from odoo import api, fields, models


class DynamicModelPreviewWizard(models.TransientModel):
    _name = 'dynamic.model.preview.wizard'
    _description = 'Wizard Preview Dynamic Model'

    dynamic_model_id = fields.Many2one(
        comodel_name='dynamic.model',
        string='Dynamic Model',
        required=True,
    )
    model_name = fields.Char(related='dynamic_model_id.name', readonly=True)
    model_code = fields.Char(related='dynamic_model_id.model_code', readonly=True)

    # Preview XML dưới dạng text
    preview_form_arch = fields.Text(
        string='Form View (Preview)',
        compute='_compute_preview',
    )
    preview_list_arch = fields.Text(
        string='List View (Preview)',
        compute='_compute_preview',
    )
    preview_field_summary = fields.Html(
        string='Tóm tắt Fields',
        compute='_compute_preview',
    )

    @api.depends('dynamic_model_id', 'dynamic_model_id.field_ids')
    def _compute_preview(self):
        for rec in self:
            model = rec.dynamic_model_id
            if not model:
                rec.preview_form_arch = ''
                rec.preview_list_arch = ''
                rec.preview_field_summary = ''
                continue

            # Build field summary table
            rows = []
            for f in model.field_ids:
                tech_name = f.field_name
                if not tech_name.startswith('x_'):
                    tech_name = f'x_{tech_name}'

                req_badge = '<span class="badge badge-danger">Required</span>' if f.required else ''
                rows.append(
                    f'<tr>'
                    f'<td><code>{tech_name}</code></td>'
                    f'<td>{f.field_label}</td>'
                    f'<td><code>{f.field_type}</code></td>'
                    f'<td>{f.relation or "-"}</td>'
                    f'<td>{req_badge}</td>'
                    f'</tr>'
                )

            rec.preview_field_summary = f"""
                <table class="table table-bordered table-sm">
                    <thead class="thead-light">
                        <tr>
                            <th>Technical Name</th>
                            <th>Label</th>
                            <th>Type</th>
                            <th>Relation</th>
                            <th>Required</th>
                        </tr>
                    </thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            """

            # Preview form arch
            form_fields = []
            for f in model.field_ids:
                tech_name = f.field_name
                if not tech_name.startswith('x_'):
                    tech_name = f'x_{tech_name}'
                form_fields.append(f'    <field name="{tech_name}" string="{f.field_label}"/>')

            rec.preview_form_arch = (
                f'<form string="{model.name}">\n'
                f'  <sheet>\n'
                f'    <group>\n'
                + '\n'.join(f'      {l}' for l in form_fields) + '\n'
                f'    </group>\n'
                f'  </sheet>\n'
                f'</form>'
            )

            # Preview tree arch
            list_fields = []
            for f in model.field_ids:
                if f.field_type in ('text', 'html', 'one2many', 'many2many', 'binary'):
                    continue
                tech_name = f.field_name
                if not tech_name.startswith('x_'):
                    tech_name = f'x_{tech_name}'
                list_fields.append(f'  <field name="{tech_name}" string="{f.field_label}"/>')

            rec.preview_list_arch = (
                f'<tree string="{model.name}">\n'
                + '\n'.join(list_fields) + '\n'
                f'</tree>'
            )

    def action_close(self):
        return {'type': 'ir.actions.act_window_close'}