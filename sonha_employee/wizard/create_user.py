from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    company_id = fields.Many2one('res.company', string="Công ty")

    def create_user_accounts(self):
        BATCH_SIZE = 100
        employee_obj = self.env['hr.employee'].sudo()
        user_obj = self.env['res.users'].sudo()

        list_employees = employee_obj.search([]).filtered(
            lambda x: x.company_id.id == self.company_id.id
        )

        # 🔥 Lấy toàn bộ login đã tồn tại (rất quan trọng)
        existing_logins = set(
            user_obj.search([]).mapped(lambda u: (u.login or '').strip().lower())
        )

        users_to_create = []

        for employee in list_employees:
            if employee.user_id:
                continue

            # 🔥 Xử lý login chuẩn
            login = (employee.work_email or employee.employee_code or '').strip().lower()

            # ❌ bỏ qua nếu không có login
            if not login:
                continue

            # ❌ bỏ qua nếu trùng
            if login in existing_logins:
                continue

            user_vals = {
                'name': employee.name,
                'login': login,
                'password': "123456",
                'email': (employee.work_email or '').strip(),
                'employee_ids': [(4, employee.id)],
                'groups_id': [(6, 0, [self.env.ref('sonha_employee.group_user_employee').id])],
            }

            users_to_create.append(user_vals)
            existing_logins.add(login)  # 🔥 tránh trùng trong cùng batch

        # 🔥 tạo theo batch (an toàn vì đã lọc trùng)
        for i in range(0, len(users_to_create), BATCH_SIZE):
            user_obj.create(users_to_create[i:i + BATCH_SIZE])

        # 🔥 link lại user
        for employee in list_employees:
            if not employee.user_id:
                login = (employee.work_email or employee.employee_code or '').strip().lower()
                if login:
                    user = user_obj.search([('login', '=', login)], limit=1)
                    if user:
                        employee.user_id = user.id

        return {'type': 'ir.actions.act_window_close'}
