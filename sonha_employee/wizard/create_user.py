from odoo import models, fields, api


class CreateUserWizard(models.TransientModel):
    _name = 'create.user.wizard'
    _description = 'Create User Accounts Wizard'

    company_id = fields.Many2one('res.company', string="Công ty")

    def create_user_accounts(self):
        BATCH_SIZE = 100  # Số lượng user tạo mỗi lần
        employee_obj = self.env['hr.employee'].sudo()
        user_obj = self.env['res.users'].sudo()

        # Lấy tất cả nhân viên cần tạo user
        list_employees = employee_obj.search(['|', ('work_email', '!=', 'nan'),
                                              ('employee_code', '!=', False)])
        list_employees = list_employees.filtered(lambda x: x.company_id.id == self.company_id.id)

        users_to_create = []  # Danh sách thông tin user cần tạo
        for employee in list_employees:
            if not employee.user_id and (employee.employee_code or employee.work_email):
                user_vals = {
                    'name': employee.name,
                    'login': employee.work_email if employee.work_email != 'nan' else employee.employee_code,
                    'password': "123456",
                    'email': employee.work_email or '',
                    'employee_ids': [(4, employee.id)],
                    'groups_id': [(6, 0, [self.env.ref('base.group_user').id])],
                }
                users_to_create.append(user_vals)

        # Xử lý tạo user theo lô
        for i in range(0, len(users_to_create), BATCH_SIZE):
            user_obj.create(users_to_create[i:i + BATCH_SIZE])

        # Cập nhật liên kết giữa nhân viên và user
        for employee in list_employees:
            if not employee.user_id and employee.employee_code:
                employee.user_id = user_obj.search(['|', ('login', '=', employee.employee_code),
                                                    ('login', '=', employee.work_email)], limit=1)

        return {
            'type': 'ir.actions.act_window_close'
        }
