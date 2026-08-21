from odoo import api, fields, models
from odoo.exceptions import ValidationError


class Project(models.Model):
    _inherit = 'project.project'

    so_du_an = fields.Char("Số dự án")
    group_du_an = fields.Char("Group dự án")
    noi_dung = fields.Text("Nội dung")
    nguoi_qlda = fields.Many2one('res.users', string="Người QLDA")
    ngay_kt_da = fields.Date("Ngày kết thúc DA")
    ngay_kt_chinh_sua = fields.Date("Ngày kết thúc chỉnh sửa")
    parent_du_an_id = fields.Many2one(
        'project.project',
        string="Dự án cha",
        index=True,
        ondelete='restrict',
        domain="[('id', '!=', id)]",
    )
    du_an_con_ids = fields.One2many(
        'project.project',
        'parent_du_an_id',
        string="Dự án con",
    )
    child_task_ids = fields.Many2many(
        'project.task',
        compute='_compute_child_task_ids',
        string="Nhiệm vụ theo dự án con",
    )
    is_parent_du_an = fields.Boolean(
        string="Là dự án cha",
        compute='_compute_is_parent_du_an',
    )

    @api.depends('du_an_con_ids')
    def _compute_is_parent_du_an(self):
        for project in self:
            project.is_parent_du_an = bool(project.du_an_con_ids)

    @api.depends('du_an_con_ids.task_ids')
    def _compute_child_task_ids(self):
        for project in self:
            project.child_task_ids = project.du_an_con_ids.mapped('task_ids')

    @api.constrains('parent_du_an_id')
    def _check_parent_du_an_id(self):
        for project in self:
            parent = project.parent_du_an_id
            while parent:
                if parent == project:
                    raise ValidationError("Dự án cha/con không được tạo vòng lặp.")
                parent = parent.parent_du_an_id
