from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ExpGroupUsers(models.Model):
    _name = 'exp.group.users'
    _rec_name = 'group_name'

    group_id = fields.Integer(string="ID nhóm người dùng", store=True)
    group_name = fields.Char(string="Tên nhóm người dùng", required=True, store=True)
    group_user_id = fields.One2many('exp.distribute.group.user', 'group_id', string="Nhân viên", store=True)
    create_access = fields.Boolean(string="Quyền tạo", store=True)
    write_access = fields.Boolean(string="Quyền sửa", store=True)
    unlink_access = fields.Boolean(string="Quyền xóa", store=True)


class ExpDistributeGroupUser(models.Model):
    _name = 'exp.distribute.group.user'
    _rec_name = 'employee_id'

    user_id = fields.Many2one('res.users', string="Nhân viên", compute="_get_emp_user", store=True)
    group_id = fields.Many2one('exp.group.users', string="Nhóm người dùng", required=True, store=True)
    employee_id = fields.Many2one('hr.employee', string="Nhân viên",
                                  domain="[('user_id', '!=', False)]", required=True, store=True)

    @api.depends('employee_id')
    def _get_emp_user(self):
        for r in self:
            if r.employee_id:
                r.user_id = r.employee_id.user_id.id
            else:
                r.user_id = None






