from odoo import models, fields, api


class MDApproveStep(models.Model):
    _name = 'md.approve.step'
    _order = 'sequence_step,id'

    sequence_step = fields.Integer("Trình tự")
    approve_role = fields.Many2one('md.approve.role', string="Vai trò")
    method = fields.Selection([('role', "Vai trò"),
                               ('parent', "Quản lý"),
                               ('assign', "Chỉ định người duyệt"),
                               ('depart_mange', "Quản lý phòng ban người tạo")], string="Phương thức")
    level = fields.Selection([('suggest', "Đề xuất"),
                              ('examine', "Thẩm tra"),
                              ('review', "Soát xét"),
                              ('approve', "Phê duyệt"),
                              ('notice', "Nhận thông báo")],
                             string="Cấp duyệt")
    employee_id = fields.Many2one('hr.employee', string="Người duyệt")
    approve_rule = fields.Many2one('md.approve.rule', string="Luồng duyệt")


