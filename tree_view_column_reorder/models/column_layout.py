from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


BUS_NOTIFICATION_TYPE = "tree_view_column_layout/updated"


class TreeViewColumnLayout(models.Model):
    _name = "tree.view.column.layout"
    _description = "Shared Tree View Column Layout"
    _order = "scope, view_id, parent_model, parent_field"

    view_id = fields.Many2one(
        "ir.ui.view",
        index=True,
        ondelete="cascade",
    )
    storage_key = fields.Char(index=True, copy=False)
    scope = fields.Selection(
        [("view", "List View"), ("x2many", "Nested List")],
        default="view",
        required=True,
        index=True,
    )
    parent_view_id = fields.Many2one("ir.ui.view", index=True, ondelete="cascade")
    parent_model = fields.Char(index=True)
    parent_field = fields.Char(index=True)
    res_model = fields.Char(index=True)
    column_order = fields.Json(default=lambda self: [])
    column_widths = fields.Json(default=lambda self: {})
    column_labels = fields.Json(default=lambda self: {})
    revision = fields.Integer(default=1, readonly=True)

    _sql_constraints = [
        ("view_id_unique", "unique(view_id)", "A column layout already exists for this view."),
        (
            "storage_key_unique",
            "unique(storage_key)",
            "A column layout already exists for this storage key.",
        ),
    ]

    @api.model
    def _storage_key_for_view(self, view_id):
        return f"view:{int(view_id)}"

    @api.model
    def _sanitize_storage_key(self, storage_key):
        if not isinstance(storage_key, str):
            raise ValidationError(_("Invalid column layout storage key."))
        storage_key = storage_key.strip()
        if not storage_key or len(storage_key) > 512:
            raise ValidationError(_("Invalid column layout storage key."))
        if not (storage_key.startswith("view:") or storage_key.startswith("x2many:")):
            raise ValidationError(_("Unsupported column layout storage key."))
        return storage_key

    @api.model
    def _prepare_storage_values(self, storage_key, layout_context=None):
        storage_key = self._sanitize_storage_key(storage_key)
        layout_context = layout_context if isinstance(layout_context, dict) else {}
        values = {"storage_key": storage_key}

        if storage_key.startswith("view:"):
            try:
                view_id = int(storage_key.split(":", 1)[1])
            except (TypeError, ValueError):
                raise ValidationError(_("Invalid view identifier."))
            view = self.env["ir.ui.view"].sudo().browse(view_id).exists()
            if not view or view.type != "tree":
                raise ValidationError(_("The selected view is not a list view."))
            values.update(
                {
                    "scope": "view",
                    "view_id": view.id,
                    "parent_view_id": False,
                    "parent_model": False,
                    "parent_field": False,
                    "res_model": view.model,
                }
            )
            return values

        parts = storage_key.split(":")
        if len(parts) < 5:
            raise ValidationError(_("Invalid nested list layout key."))
        try:
            parent_view_id = int(parts[1])
        except (TypeError, ValueError):
            raise ValidationError(_("Invalid parent view identifier."))
        parent_view = self.env["ir.ui.view"].sudo().browse(parent_view_id).exists()
        if not parent_view or parent_view.type != "form":
            raise ValidationError(_("The parent view is not a form view."))

        parent_model = str(layout_context.get("parentModel") or parts[2] or "")[:128]
        parent_field = str(layout_context.get("parentField") or parts[3] or "")[:128]
        res_model = str(layout_context.get("resModel") or ":".join(parts[4:]) or "")[:128]
        if not parent_model or not parent_field or not res_model:
            raise ValidationError(_("Invalid nested list layout context."))

        values.update(
            {
                "scope": "x2many",
                "view_id": False,
                "parent_view_id": parent_view.id,
                "parent_model": parent_model,
                "parent_field": parent_field,
                "res_model": res_model,
            }
        )
        return values

    @api.model
    def _sanitize_column_order(self, column_order):
        if not isinstance(column_order, list):
            raise ValidationError(_("Column order must be a list."))
        result = []
        for name in column_order:
            if isinstance(name, str) and name and name not in result:
                result.append(name[:128])
        return result[:500]

    @api.model
    def _sanitize_width_updates(self, width_updates):
        if not isinstance(width_updates, dict):
            raise ValidationError(_("Column width updates must be an object."))
        result = {}
        for name, width in width_updates.items():
            if not isinstance(name, str) or not name:
                continue
            if width is None or width is False:
                result[name[:128]] = None
                continue
            if isinstance(width, bool) or not isinstance(width, (int, float)):
                continue
            result[name[:128]] = max(24, min(2000, round(width)))
        return result

    @api.model
    def _sanitize_label_updates(self, label_updates):
        if not isinstance(label_updates, dict):
            raise ValidationError(_("Column label updates must be an object."))
        result = {}
        for key, label in label_updates.items():
            if not isinstance(key, str) or not key:
                continue
            key = key[:160]
            if label is None or label is False:
                result[key] = None
                continue
            if not isinstance(label, str):
                continue
            label = label.strip()
            result[key] = label[:128] if label else None
        return result

    def _format_layout(self):
        self.ensure_one()
        storage_key = self.storage_key or (
            self.view_id and self._storage_key_for_view(self.view_id.id)
        )
        return {
            "storageKey": storage_key,
            "viewId": self.view_id.id,
            "resModel": self.res_model,
            "scope": self.scope,
            "parentViewId": self.parent_view_id.id,
            "parentModel": self.parent_model,
            "parentField": self.parent_field,
            "order": self.column_order if isinstance(self.column_order, list) else [],
            "widths": self.column_widths if isinstance(self.column_widths, dict) else {},
            "labels": self.column_labels if isinstance(self.column_labels, dict) else {},
            "revision": self.revision,
        }

    @api.model
    def _get_layout_map(self):
        result = {}
        for layout in self.sudo().search([]):
            formatted = layout._format_layout()
            if formatted["storageKey"]:
                result[formatted["storageKey"]] = formatted
        return result

    @api.model
    def save_layout(
        self,
        view_id,
        column_order=None,
        width_updates=None,
        label_updates=None,
        reset=False,
    ):
        return self.save_layout_by_key(
            self._storage_key_for_view(view_id),
            column_order=column_order,
            width_updates=width_updates,
            label_updates=label_updates,
            reset=reset,
        )

    @api.model
    def save_layout_by_key(
        self,
        storage_key,
        layout_context=None,
        column_order=None,
        width_updates=None,
        label_updates=None,
        reset=False,
    ):
        if not self.env.user._is_admin():
            raise AccessError(_("Only administrators can change shared column layouts."))

        storage_values = self._prepare_storage_values(storage_key, layout_context)

        layout = self.sudo().search(
            [("storage_key", "=", storage_values["storage_key"])], limit=1
        )
        if not layout and storage_values.get("view_id"):
            layout = self.sudo().search([("view_id", "=", storage_values["view_id"])], limit=1)
        values = {
            **storage_values,
            "revision": (layout.revision if layout else 0) + 1,
        }

        if reset:
            values.update({"column_order": [], "column_widths": {}, "column_labels": {}})
        else:
            if column_order is not None:
                values["column_order"] = self._sanitize_column_order(column_order)
            if width_updates is not None:
                widths = dict(layout.column_widths or {}) if layout else {}
                for name, width in self._sanitize_width_updates(width_updates).items():
                    if width is None:
                        widths.pop(name, None)
                    else:
                        widths[name] = width
                values["column_widths"] = widths
            if label_updates is not None:
                labels = dict(layout.column_labels or {}) if layout else {}
                for key, label in self._sanitize_label_updates(label_updates).items():
                    if label is None:
                        labels.pop(key, None)
                    else:
                        labels[key] = label
                values["column_labels"] = labels

        if layout:
            layout.write(values)
        else:
            layout = self.sudo().create(values)

        payload = layout._format_layout()
        self.env["bus.bus"].sudo()._sendone("broadcast", BUS_NOTIFICATION_TYPE, payload)
        return payload
