from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta, date


class Project(models.Model):
    _inherit = 'project.project'

    so_du_an = fields.Char("Số dự án", store=True)
    group_du_an = fields.Many2one(
        'group.du.an',
        string="Group dự án", store=True
    )
    noi_dung = fields.Text("Nội dung", store=True)
    nguoi_qlda = fields.Many2many('res.users', 'ir_qlda_group_rel',
                                  'qlda_group_rel', 'qlda_rel', string='Người QLDA', store=True)
    ngay_kt_da = fields.Date("Ngày kết thúc DA", store=True, readonly=False)
    ngay_kt_chinh_sua = fields.Date("Ngày kết thúc chỉnh sửa", store=True)
    du_an_cha = fields.Boolean("Dự án cha", default=True, store=True)
    du_an_cha_id = fields.Many2one(
        'project.project',
        string="Dự án cha",
        index=True,
        ondelete='restrict', store=True
    )
    ty_le_phan_tram = fields.Float("%", store=True)
    du_an_con_ids = fields.One2many(
        'project.project',
        'du_an_cha_id',
        string="Dự án con", store=True
    )
    nhiem_vu_du_an_ids = fields.One2many(
        'project.task',
        'du_an_cha_task_id',
        string="Nhiệm vụ", store=True
    )

    ten = fields.Char("Tên dự án", store=True, compute="get_name_duan")

    ngay_bat_dau = fields.Date("Ngày bắt đầu", store=True, required=True)

    trang_thai = fields.Selection([('run', 'Đang chạy'), ('kt', 'Kết thúc')],
                                  string='Trạng thái',
                                  default='run',  store=True)

    ngay_kt_da_tt = fields.Date("Ngày kết thúc dự án thực rế", store=True)

    @api.depends('name')
    def get_name_duan(self):
        for r in self:
            if r.name:
                r.ten = r.name

    # @api.model
    # def _read_group_group_du_an(self, groups, domain, order):
    #     """Keep every configured project group visible on the Kanban board."""
    #     return self.env['group.du.an'].search([], order=order)

    @api.onchange('du_an_cha_id')
    def _onchange_du_an_cha_id(self):
        for project in self:
            if project.du_an_cha_id:
                project.du_an_cha = False
                project.ngay_kt_chinh_sua = project.du_an_cha_id.ngay_kt_chinh_sua

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('du_an_cha_id'):
                vals['du_an_cha'] = False
                parent = self.env['project.project'].browse(vals['du_an_cha_id'])
                vals['ngay_kt_chinh_sua'] = parent.ngay_kt_chinh_sua
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('sync_parent_end_date'):
            today = fields.Date.context_today(self)
            for record in self:
                if record.ngay_kt_chinh_sua and record.ngay_kt_chinh_sua < today:
                    raise ValidationError(
                        'Bản ghi đã quá ngày %s nên không được phép chỉnh sửa.'
                        % record.date.strftime('%d/%m/%Y')
                    )

        # A child project's end date is inherited from its parent.  Write each
        # record separately because a multi-record write can contain children
        # belonging to different parents.
        if 'du_an_cha_id' in vals or 'ngay_kt_chinh_sua' in vals:
            for record in self:
                record_vals = dict(vals)
                parent_id = record_vals.get('du_an_cha_id', record.du_an_cha_id.id)
                if parent_id:
                    parent = self.env['project.project'].browse(parent_id)
                    record_vals.update(
                        du_an_cha=False,
                        ngay_kt_chinh_sua=parent.ngay_kt_chinh_sua,
                    )
                super(Project, record).write(record_vals)
                if 'ngay_kt_chinh_sua' in record_vals:
                    record._sync_child_project_end_dates()
            return True

        return super().write(vals)

    def _sync_child_project_end_dates(self):
        """Propagate this project's end date to every direct child project."""
        for project in self:
            project.du_an_con_ids.with_context(sync_parent_end_date=True).write({
                'ngay_kt_chinh_sua': project.ngay_kt_chinh_sua,
            })

    def _validate_ty_le_phan_tram(self):
        for project in self:
            if not project.du_an_cha_id:
                continue
            if project.ty_le_phan_tram <= 0:
                raise ValidationError(
                    _("Bạn bắt buộc phải nhập % lớn hơn 0 cho dự án con.")
                )
            if project.ty_le_phan_tram > 100:
                raise ValidationError(
                    _("% của dự án con không được lớn hơn 100%.")
                )
            siblings = self.search([
                ('du_an_cha_id', '=', project.du_an_cha_id.id),
            ])
            total_percent = sum(siblings.mapped('ty_le_phan_tram'))
            if total_percent > 100:
                raise ValidationError(
                    _("Tổng % của tất cả dự án con không được vượt quá 100%.")
                )

    @api.constrains('ty_le_phan_tram', 'du_an_cha_id')
    def _check_ty_le_phan_tram(self):
        self._validate_ty_le_phan_tram()

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
                and project.ngay_kt_da != project.du_an_cha_id.ngay_kt_da
            ):
                raise ValidationError(
                    _(
                        "Ngày kết thúc dự án con phải bằng ngày kết thúc dự án cha."
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
        self._validate_child_task_end_dates()

    @api.constrains('ty_le_phan_tram')
    def _check_child_task_percent(self):
        tasks = self.env['project.task'].search([('cap', 'in', self.ids)])
        if tasks:
            tasks._validate_ty_le_phan_tram()

    def action_view_tasks(self):
        """Open base Project tasks with the fixed workflow Kanban.

        The native Project action can select another Kanban view depending on
        its action configuration.  Explicitly selecting our inherited view
        makes the four fixed columns apply when users enter tasks from the
        standard Project application as well as from custom project screens.
        """
        action = super().action_view_tasks()
        fixed_kanban_view = self.env.ref(
            'sonha_du_an.view_task_kanban_fixed_stages'
        )
        action['views'] = [(fixed_kanban_view.id, 'kanban')] + [
            view for view in action.get('views', []) if view[1] != 'kanban'
        ]
        context = dict(action.get('context') or {})
        context['group_by'] = 'trang_thai'
        action['context'] = context
        return action

    def action_ket_thuc(self):
        for r in self:
            r.trang_thai = 'kt'
            r.ngay_kt_da_tt = date.today()
