from odoo import models, fields, api, tools
from odoo.exceptions import ValidationError


class MenuAccessControl(models.Model):
    _name = 'menu.access.control'

    user_id = fields.Many2one('res.users', string="Người dùng", store=True)
    menu_id = fields.Many2one('ir.ui.menu', string="Menu", store=True)
    can_see = fields.Boolean(string="Có thể thấy", store=True)

    @api.constrains('user_id', 'menu_id')
    def validate_record(self):
        for r in self:
            dup = self.sudo().search([
                ('user_id', '=', r.user_id.id),
                ('menu_id', '=', r.menu_id.id),
                ('id', '!=', r.id)
            ])
            if dup:
                raise ValidationError("Người dùng này đã có quyền truy cập tới menu này rồi!")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Xoá cache khi có thay đổi
        self.env['ir.ui.menu'].clear_caches()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.env['ir.ui.menu'].clear_caches()
        return res

    def unlink(self):
        res = super().unlink()
        self.env['ir.ui.menu'].clear_caches()
        return res


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    def _visible_menu_ids(self, debug=False):
        visible_ids = super()._visible_menu_ids(debug=debug)
        uid = self.env.uid

        # Lấy rules từ cache
        force_show, force_hide = self._get_access_rules_cached(uid)

        if not force_show and not force_hide:
            return visible_ids

        # Lấy menu tree từ cache
        menu_map, children_map = self._get_menu_tree_cached()

        visible_set = set(visible_ids)

        # Bước 1: Ẩn menu bị force hide (cả cây con)
        if force_hide:
            to_hide = self._get_all_children_sql(force_hide, children_map)
            to_hide -= force_show
            visible_set -= to_hide

        # Bước 2: Thêm force show
        visible_set |= force_show

        # Bước 3: Thêm tổ tiên của force show
        ancestor_ids = set()
        for menu_id in force_show:
            pid = menu_map.get(menu_id)
            while pid:
                ancestor_ids.add(pid)
                pid = menu_map.get(pid)
        visible_set |= ancestor_ids

        # Bước 4: Lọc - chỉ giữ menu hợp lệ
        original_set = set(visible_ids)
        final_set = set()
        for mid in visible_set:
            if mid in original_set:
                final_set.add(mid)
            elif mid in force_show:
                final_set.add(mid)
            elif mid in ancestor_ids:
                final_set.add(mid)

        return list(final_set)

    @tools.ormcache('uid')
    def _get_access_rules_cached(self, uid):
        """Cache rules theo từng user. Chỉ query DB 1 lần cho mỗi user."""
        self.env.cr.execute("""
            SELECT menu_id, can_see
            FROM menu_access_control
            WHERE user_id = %s
        """, (uid,))
        rows = self.env.cr.fetchall()
        force_show = frozenset(r[0] for r in rows if r[1])
        force_hide = frozenset(r[0] for r in rows if not r[1])
        return force_show, force_hide

    @tools.ormcache()
    def _get_menu_tree_cached(self):
        """Cache toàn bộ menu tree. Dùng chung cho mọi user."""
        self.env.cr.execute("SELECT id, parent_id FROM ir_ui_menu")
        rows = self.env.cr.fetchall()
        menu_map = {row[0]: row[1] for row in rows}
        children_map = {}
        for mid, pid in menu_map.items():
            if pid:
                children_map.setdefault(pid, []).append(mid)
        return menu_map, children_map

    def _get_all_children_sql(self, menu_ids, children_map):
        """Lấy toàn bộ cây con, không dùng ORM."""
        result = set(menu_ids)
        queue = list(menu_ids)
        while queue:
            current = queue.pop()
            for child in children_map.get(current, []):
                if child not in result:
                    result.add(child)
                    queue.append(child)
        return result