from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class DeclareMDSaleman(models.Model):
    _name = 'declare.md.saleman'
    _rec_name = 'display_name'

    code = fields.Char("Mã NVKD")
    name = fields.Char("Tên NVKD", required=True)
    company_id = fields.Many2one('res.company', string="Đơn vị")
    display_name = fields.Char(compute="compute_display_name", store=True)
    type = fields.Selection([('emp', "Nhân viên"),
                             ('asmr', "Quản lý vùng"),
                             ('rsm', "Quản lý khu vực")], string="Loại NVKD")

    # status = fields.Selection([('draft', "Nháp"),
    #                            ('waiting', "Chờ duyệt"),
    #                            ('done', "Đã duyệt")], string="Trạng thái", default='draft')
    # next_approve_employee = fields.Many2many('hr.employee', string="Người duyệt")
    # employee_id = fields.Many2one('hr.employee', string="Người tạo", default=lambda self: self.get_create_employee())
    # md_approve_display = fields.One2many('md.approve.display', 'md_saleman', string="Quy trình duyệt")

    # def get_create_employee(self):
    #     employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)])
    #     if employee:
    #         return employee.id
    #
    @api.depends('code', 'name')
    def compute_display_name(self):
        for r in self:
            if r.code and r.name:
                r.display_name = f"{r.code} - {r.name}"
            else:
                r.display_name = None
    #
    # def get_approve_people(self, record, employee):
    #     admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
    #     approve_people = admin
    #     employee_id = self.env['hr.employee'].sudo().search([('id', '=', employee.id)])
    #     if record.method == 'role':
    #         if record.approve_role and record.approve_role.approve_employee:
    #             approve_people = record.approve_role.approve_employee
    #     elif record.method == 'assign':
    #         if record.employee_id:
    #             approve_people = record.employee_id
    #     elif record.method == 'parent':
    #         if employee_id.parent_id:
    #             approve_people = employee_id.parent_id
    #     else:
    #         if employee_id.department_id and employee_id.department_id.manager_id:
    #             approve_people = employee_id.department_id.manager_id
    #     return approve_people
    #
    # def get_approve_employee(self):
    #     for r in self:
    #         list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
    #         if list_suggest and r.status == 'draft':
    #             next_approve_people = list_suggest.mapped('employee_id')
    #         else:
    #             list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'] and x.status == 'waiting')
    #             list_approve = list_approve.sorted(key=lambda x: (x.sequence_step, x.id))
    #             next_approve_people = list_approve[0].employee_id
    #         return next_approve_people
    #
    # def action_approve(self):
    #     for r in self:
    #         if r.status == 'waiting':
    #             if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
    #                 list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['examine', 'notice'] and x.status == 'waiting')
    #                 if len(list_approve) == 1:
    #                     list_approve[0].sudo().write({'status': 'done'})
    #                     r.status = 'done'
    #                     vals = {
    #                         'code': r.code,
    #                         'name': r.name,
    #                         'company_id': r.company_id.id,
    #                         'declare_saleman': r.id,
    #                     }
    #                     md = self.env['md.saleman'].sudo().create(vals)
    #                 else:
    #                     list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
    #                     if list_suggest:
    #                         list_suggest.sudo().write({'status': 'done'})
    #                     else:
    #                         list_approve[0].sudo().write({'status': 'done'})
    #                     next_approve_people = r.get_approve_employee()
    #                     r.next_approve_employee = next_approve_people
    #             else:
    #                 raise ValidationError("Bạn không có quyền duyệt bước này!")
    #         else:
    #             raise ValidationError("Bạn không thể duyệt bản ghi này!")
    #
    # def action_sent(self):
    #     for r in self:
    #         if r.employee_id.user_id.id == self.env.uid or self.env.uid == 2:
    #             model_id = self.env['ir.model'].sudo().search([('model', '=', 'declare.md.saleman')], limit=1).id
    #             approve_rule = self.env['md.approve.rule'].sudo().search([('model_apply', '=', model_id),
    #                                                                       ('company_ids', 'in', r.company_id.id)])
    #             if approve_rule:
    #                 for record in approve_rule.step:
    #                     approve_emp = self.get_approve_people(record, r.employee_id)
    #                     val = {
    #                         'sequence_step': record.sequence_step,
    #                         'level': record.level,
    #                         'employee_id': approve_emp.id,
    #                         'md_saleman': r.id,
    #                     }
    #                     self.env['md.approve.display'].sudo().create(val)
    #                 approve_record = approve_rule.step.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'])
    #                 if not approve_record:
    #                     admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
    #                     val = {
    #                         'sequence_step': len(approve_rule.step) + 1,
    #                         'level': 'approve',
    #                         'employee_id': admin.id,
    #                         'md_saleman': r.id,
    #                     }
    #                     self.env['md.approve.display'].sudo().create(val)
    #             else:
    #                 admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
    #                 val = {
    #                     'sequence_step': 1,
    #                     'level': 'approve',
    #                     'employee_id': admin.id,
    #                     'md_saleman': r.id,
    #                 }
    #                 self.env['md.approve.display'].sudo().create(val)
    #             r.next_approve_employee = r.get_approve_employee()
    #             r.status = 'waiting'
    #         else:
    #             raise ValidationError("Bạn không có quyền thực hiện hành động này!")
    #
    # def to_draft_action(self):
    #     for r in self:
    #         if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
    #             r.next_approve_employee = None
    #             r.status = 'draft'
    #             record = self.env['md.saleman'].sudo().search([('declare_saleman', '=', r.id)])
    #             if record:
    #                 record.sudo().unlink()
    #             self.env['md.approve.display'].sudo().search([('md_saleman', '=', r.id)]).unlink()
    #         else:
    #             raise ValidationError("Bạn không có quyền thực hiện hành động này!")
    #
    # def unlink(self):
    #     for r in self:
    #         if r.status != 'draft':
    #             raise ValidationError("Chỉ được xóa khi là ở trạng thái nháp!")
    #     return super(DeclareMDSaleman, self).unlink()

