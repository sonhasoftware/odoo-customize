from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Task(models.Model):
    _inherit = 'project.task'

    du_an_cha_task_id = fields.Many2one(
        'project.project',
        string="Dự án cha",
        index=True,
        ondelete='cascade',
    )
    cap = fields.Many2one(
        'project.project',
        string="Dự án con",
    )
    noi_dung_cv = fields.Text("Nội dung công việc", store=True)
    so_ngay_ht = fields.Float("Số ngày hoàn thành", required=True, store=True)
    ngay_bat_dau = fields.Date("Ngày bắt đầu", required=True, store=True)
    ngay_ket_thuc = fields.Date("Ngày kết thúc", compute="get_ngay_ket_thuc", store=True)
    ngay_hoan_thanh = fields.Date("Ngày hoàn thành", store=True)
    so_ngay_pending = fields.Float("Số ngày Pending", store=True)

    ns_lam = fields.Many2many('res.users', 'ir_ns_lam_group_rel',
                                  'ns_lam_group_rel', 'ns_lam_rel', string='NS làm', store=True)

    chu_so_huu = fields.Many2many('res.users', 'ir_chu_so_huu_group_rel',
                                  'chu_so_huu_group_rel', 'chu_so_huu_rel', string='Chủ sở hữu', store=True)

    trang_thai = fields.Selection([('kt', 'Khởi tạo'), ('run', 'Đang chạy'),
                                   ('ht', 'Hoàn thành'), ('pd', 'Pending')],
                                  string='Trạng thái',
                                  default='kt',
                                  group_expand='_group_expand_trang_thai', store=True)

    @api.model
    def _group_expand_trang_thai(self, states, domain, order):
        return [
            'kt',
            'run',
            'ht',
            'pd',
        ]

    def _get_project_end_date_limit(self):
        self.ensure_one()
        if self.cap and self.cap.ngay_kt_da:
            return self.cap.ngay_kt_da, self.cap
        if self.du_an_cha_task_id and self.du_an_cha_task_id.ngay_kt_da:
            return self.du_an_cha_task_id.ngay_kt_da, self.du_an_cha_task_id
        return False, self.env['project.project']

    def _validate_project_end_dates(self):
        for task in self:
            limit_date, project = task._get_project_end_date_limit()
            if task.ngay_ket_thuc and limit_date and task.ngay_ket_thuc > limit_date:
                if task.cap and project == task.cap:
                    message = _(
                        "Ngày kết thúc nhiệm vụ không được lớn hơn ngày kết thúc dự án con."
                    )
                else:
                    message = _(
                        "Ngày kết thúc nhiệm vụ không được lớn hơn ngày kết thúc dự án cha."
                    )
                raise ValidationError(message)

    @api.constrains('cap', 'du_an_cha_task_id', 'so_ngay_ht', 'ngay_bat_dau', 'so_ngay_pending')
    def _check_ngay_ket_thuc_with_project(self):
        self._validate_project_end_dates()

    @api.onchange('cap')
    def _onchange_cap(self):
        if self.cap:
            self.project_id = self.cap
            self.du_an_cha_task_id = self.cap

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Do not let a project-specific default stage reintroduce custom
            # workflow columns when tasks are created from the standard Project app.
            if not vals.get('stage_id'):
                vals['stage_id'] = self._get_default_stage_id()
            if vals.get('cap'):
                vals['project_id'] = vals['cap']
                if not vals.get('du_an_cha_task_id'):
                    vals['du_an_cha_task_id'] = self.env['project.project'].browse(vals['cap']).du_an_cha_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('cap'):
            vals = dict(vals, project_id=vals['cap'])
            if not vals.get('du_an_cha_task_id'):
                vals['du_an_cha_task_id'] = self.env['project.project'].browse(vals['cap']).du_an_cha_id.id
        return super().write(vals)

    @api.depends('so_ngay_ht', 'ngay_bat_dau', 'so_ngay_pending')
    def get_ngay_ket_thuc(self):
        for r in self:
            if r.so_ngay_pending > 0 and r.so_ngay_ht and r.ngay_bat_dau:
                r.ngay_ket_thuc = r.ngay_bat_dau + timedelta(days=(r.so_ngay_ht + r.so_ngay_pending))
            elif r.so_ngay_pending <= 0 and r.so_ngay_ht and r.ngay_bat_dau:
                r.ngay_ket_thuc = r.ngay_bat_dau + timedelta(days=r.so_ngay_ht)
            else:
                r.ngay_ket_thuc = False

    def action_run(self):
        for r in self:
            r.trang_thai = 'run'

    def action_done(self):
        for r in self:
            r.trang_thai = 'done'

    def action_reset(self):
        for r in self:
            r.trang_thai = 'kt'

    def action_tam_dung(self):
        for r in self:
            r.trang_thai = 'pd'
