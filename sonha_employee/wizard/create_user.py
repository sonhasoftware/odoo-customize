from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    def create_user_accounts(self):
        list_employees = self.env['hr.employee'].sudo().search([])  # Lấy tất cả nhân viên
        users_to_create = []  # Danh sách chứa thông tin người dùng mới

        for employee in list_employees:
            if not employee.user_id and employee.employee_code:  # Kiểm tra nếu nhân viên chưa có user
                user_vals = {
                    'name': employee.name,
                    'login': employee.employee_code,  # Đặt login là mã nhân viên
                    'password': employee.employee_code,  # Đặt password là mã nhân viên
                    'email': employee.work_email or '',  # Email nếu có
                    'employee_ids': [(4, employee.id)],  # Liên kết với nhân viên
                    'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],  # Quyền của user bình thường
                }
                users_to_create.append(user_vals)  # Thêm vào danh sách người dùng mới

        # Tạo tất cả người dùng trong một lần
        if users_to_create:
            self.env['res.users'].sudo().create(users_to_create)

        # Cập nhật liên kết giữa nhân viên và người dùng
        for employee in list_employees:
            if not employee.user_id and employee.employee_code:
                employee.user_id = self.env['res.users'].sudo().search([('login', '=', employee.employee_code)],
                                                                       limit=1)

        return {
            'type': 'ir.actions.act_window_close'
        }