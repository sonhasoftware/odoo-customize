from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    def create_user_accounts(self):
        list_employees = self.env['hr.employee'].sudo().search([])
        for employee in list_employees:  # Lặp qua tất cả nhân viên
            if not employee.user_id and employee.employee_code:  # Kiểm tra nếu nhân viên chưa có user
                user_vals = {
                    'name': employee.name,
                    'login': employee.employee_code,  # Đặt login là mã nhân viên
                    'password': employee.employee_code,  # Đặt password là mã nhân viên
                    'email': employee.work_email or '',  # Email nếu có
                    'employee_ids': [(4, employee.id)],  # Liên kết với nhân viên
                    'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],  # Quyền của user bình thường
                }
                user = self.env['res.users'].create(user_vals)
                employee.user_id = user  # Liên kết user với nhân viên

        return {
            'type': 'ir.actions.act_window_close'
        }