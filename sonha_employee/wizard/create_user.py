from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    def create_user_accounts(self):
        list_employees = self.env['hr.employee'].sudo().search(['|', ('work_email', '!=', 'nan'),
                                                                ('employee_code', '!=', False)])  # Lấy tất cả nhân viên
        users_to_create = []  # Danh sách chứa thông tin người dùng mới

        for employee in list_employees:
            if not employee.user_id and (employee.employee_code or employee.work_email):  # Kiểm tra nếu nhân viên chưa có user
                user_vals = {
                    'name': employee.name,
                    'login': employee.work_email if employee.work_email != 'nan' else employee.employee_code,
                    'password': "123456",
                    'email': employee.work_email or '',
                    'employee_ids': [(4, employee.id)],
                    'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
                }
                users_to_create.append(user_vals)

        # Tạo tất cả người dùng trong một lần
        if users_to_create:
            self.env['res.users'].sudo().create(users_to_create)

        # Cập nhật liên kết giữa nhân viên và người dùng
        for employee in list_employees:
            if not employee.user_id and employee.employee_code:
                employee.user_id = self.env['res.users'].sudo().search(['|', ('login', '=', employee.employee_code),
                                                                        ('login', '=', employee.work_email)], limit=1)

        return {
            'type': 'ir.actions.act_window_close'
        }