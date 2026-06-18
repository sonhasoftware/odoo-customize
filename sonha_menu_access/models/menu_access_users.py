from odoo import models, fields, api


class MenuAccessUsers(models.Model):
    _name = 'menu.access.users'

    user_id = fields.Many2one('res.users', string="Người dùng", store=True)
    module = fields.Char(string="Module", store=True)

    def action_create_access(self):
        menu_access = self.env['menu.access.control'].sudo()

        for rec in self:
            if not rec.user_id or not rec.module:
                continue

            # Lấy tất cả menu có XML ID bắt đầu bằng 'menu_exp_'
            self.env.cr.execute("""
                SELECT res_id
                FROM ir_model_data
                WHERE model = 'ir.ui.menu'
                  AND module = %s
            """, (rec.module, ))
            menu_ids = [row[0] for row in self.env.cr.fetchall()]

            if not menu_ids:
                continue

            # Lấy những menu đã tồn tại rule để tránh duplicate
            existing = menu_access.search([
                ('user_id', '=', rec.user_id.id),
                ('menu_id', 'in', menu_ids)
            ])
            existing_menu_ids = set(existing.mapped('menu_id').ids)

            # Tạo mới những menu chưa có
            vals_list = []
            for mid in menu_ids:
                if mid not in existing_menu_ids:
                    vals_list.append({
                        'user_id': rec.user_id.id,
                        'menu_id': mid,
                        'can_see': True
                    })

            if vals_list:
                menu_access.create(vals_list)

        # clear cache để áp dụng ngay
        self.env['ir.ui.menu'].clear_caches()
