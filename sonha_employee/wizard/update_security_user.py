from odoo import models, fields, api


class UpdateSecurityUser(models.TransientModel):
    _name = 'update.security.user'
    _description = 'Update Security User'

    company_id = fields.Many2one('res.company', string="Công ty")

    def update_user_accounts(self):
        custom_group = self.env.ref('sonha_employee.group_user_employee')

        if not custom_group:
            raise ValueError("Nhóm quyền không tồn tại!")

        # Lấy tất cả nhân viên
        employees = self.env['res.users'].search([('company_id', '=', self.company_id.id)])

        for employee in employees:
            if custom_group.id not in employee.groups_id.ids:
                employee.write({'groups_id': [(4, custom_group.id)]})

        return True