from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Project(models.Model):
    _inherit = 'project.project'

    so_du_an = fields.Char("Số dự án")
    group_du_an = fields.Many2one(
        'group.du.an',
        string="Group dự án",
        group_expand='_read_group_group_du_an',
    )
    noi_dung = fields.Text("Nội dung")
    nguoi_qlda = fields.Many2many('res.users', 'ir_qlda_group_rel',
                                  'qlda_group_rel', 'qlda_rel', string='Người QLDA')
    ngay_kt_da = fields.Date("Ngày kết thúc DA")
    ngay_kt_chinh_sua = fields.Date("Ngày kết thúc chỉnh sửa")
    du_an_cha = fields.Boolean("Dự án cha", default=True)
    du_an_cha_id = fields.Many2one(
        'project.project',
        string="Dự án cha",
        index=True,
        ondelete='restrict',
    )
    du_an_con_ids = fields.One2many(
        'project.project',
        'du_an_cha_id',
        string="Dự án con",
    )
    nhiem_vu_du_an_ids = fields.One2many(
        'project.task',
        'du_an_cha_task_id',
        string="Nhiệm vụ",
    )

    @api.model
    def _read_group_group_du_an(self, groups, domain, order):
        """Keep every configured project group visible on the Kanban board."""
        return self.env['group.du.an'].search([], order=order)

    @api.onchange('du_an_cha_id')
    def _onchange_du_an_cha_id(self):
        for project in self:
            if project.du_an_cha_id:
                project.du_an_cha = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('du_an_cha_id'):
                vals['du_an_cha'] = False
        return super().create(vals_list)

    def write(self, vals):
        today = fields.Date.context_today(self)
        for record in self:
            if record.ngay_kt_chinh_sua and record.ngay_kt_chinh_sua < today:
                raise ValidationError(
                    'Bản ghi đã quá ngày %s nên không được phép chỉnh sửa.'
                    % record.date.strftime('%d/%m/%Y')
                )
        if vals.get('du_an_cha_id'):
            vals = dict(vals, du_an_cha=False)
        return super().write(vals)

    @api.constrains('du_an_cha_id')
    def _check_du_an_cha_id(self):
        for project in self:
            parent = project.du_an_cha_id
            while parent:
                if parent == project:
                    raise ValidationError(
                        _("Dự án cha không được tạo thành vòng lặp với dự án con.")
                    )
                parent = parent.du_an_cha_id

    def _validate_child_project_end_dates(self):
        for project in self:
            if (
                project.du_an_cha_id
                and project.ngay_kt_da
                and project.du_an_cha_id.ngay_kt_da
                and project.ngay_kt_da > project.du_an_cha_id.ngay_kt_da
            ):
                raise ValidationError(
                    _(
                        "Ngày kết thúc dự án con không được lớn hơn ngày kết thúc dự án cha."
                    )
                )

    def _validate_child_task_end_dates(self):
        tasks = self.env['project.task']
        for project in self:
            tasks |= project.nhiem_vu_du_an_ids
            tasks |= self.env['project.task'].search([
                '|',
                ('cap', '=', project.id),
                ('du_an_cha_task_id', '=', project.id),
            ])
        if tasks:
            tasks._validate_project_end_dates()

    @api.constrains('du_an_cha_id', 'ngay_kt_da')
    def _check_ngay_kt_da_with_parent(self):
        self._validate_child_project_end_dates()
        self.mapped('du_an_con_ids')._validate_child_project_end_dates()
        self._validate_child_task_end_dates()

    def action_luu_tam(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đã lưu tạm'),
                'message': _('Dữ liệu dự án đã được lưu tạm, bạn có thể chọn ở trường Dự án con.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_view_tasks(self):
        """Open this project's tasks as a board grouped by their stages.

        Tasks created from this module belong to a child project in Odoo's
        standard ``project_id`` field.  ``du_an_cha_task_id`` is therefore the
        reliable link back to the project card selected on the main board.
        """
        action = super().action_view_tasks()
        if len(self) == 1:
            action['domain'] = [('du_an_cha_task_id', '=', self.id)]
            context = dict(action.get('context') or {})
            context.update({
                'default_project_id': self.id,
                'default_du_an_cha_task_id': self.id,
                # A task board is most useful when its workflow columns are
                # visible immediately, rather than inheriting a previous
                # user-selected grouping from another task screen.
                'group_by': 'stage_id',
            })
            action['context'] = context
        return action
