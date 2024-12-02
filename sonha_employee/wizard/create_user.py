from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    def create_user_accounts(self):
        employee_obj = self.env['hr.employee'].sudo()
        user_obj = self.env['res.users'].sudo()

        # Lấy tất cả nhân viên cần tạo user
        list_employees = employee_obj.search(['|', ('work_email', '!=', 'nan'),
                                              ('employee_code', '!=', False), ('user_id', '=', False)])

        # Tạo user
        users_to_create = [{
            'name': emp.name,
            'login': emp.work_email if emp.work_email != 'nan' else emp.employee_code,
            'password': "123456",
            'email': emp.work_email or '',
            'employee_ids': [(4, emp.id)],
            'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
        } for emp in list_employees]

        if users_to_create:
            created_users = user_obj.create(users_to_create)

        # Liên kết user với nhân viên
        if created_users:
            for user, emp in zip(created_users, list_employees):
                emp.user_id = user

        return {
            'type': 'ir.actions.act_window_close'
        }
