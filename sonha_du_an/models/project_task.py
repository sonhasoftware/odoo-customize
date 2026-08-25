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
    noi_dung_cv = fields.Text("Nội dung công việc")
    so_ngay_ht = fields.Float("Số ngày hoàn thành", required=True)
    ngay_bat_dau = fields.Date("Ngày bắt đầu", required=True)
    ngay_ket_thuc = fields.Date("Ngày kết thúc", compute="get_ngay_ket_thuc")
    ngay_hoan_thanh = fields.Date("Ngày hoàn thành")
    so_ngay_pending = fields.Float("Số ngày Pending")

    ns_lam = fields.Many2many('res.users', 'ir_ns_lam_group_rel',
                                  'ns_lam_group_rel', 'ns_lam_rel', string='NS làm')

    chu_so_huu = fields.Many2many('res.users', 'ir_chu_so_huu_group_rel',
                                  'chu_so_huu_group_rel', 'chu_so_huu_rel', string='Chủ sở hữu')

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        """Restrict the standard task Kanban to the four approved stages."""
        return self.env['project.task.type'].browse([
            self.env.ref('sonha_du_an.task_stage_khoi_tao').id,
            self.env.ref('sonha_du_an.task_stage_dang_chay').id,
            self.env.ref('sonha_du_an.task_stage_ket_thuc').id,
            self.env.ref('sonha_du_an.task_stage_tam_dung').id,
        ])

    @api.model
    def _get_default_stage_id(self):
        return self.env.ref('sonha_du_an.task_stage_khoi_tao').id

    def _set_stage(self, stage_xmlid):
        self.ensure_one()
        self.stage_id = self.env.ref(stage_xmlid)

    def action_set_khoi_tao(self):
        self._set_stage('sonha_du_an.task_stage_khoi_tao')

    def action_set_dang_chay(self):
        self._set_stage('sonha_du_an.task_stage_dang_chay')

    def action_set_ket_thuc(self):
        self._set_stage('sonha_du_an.task_stage_ket_thuc')

    def action_set_tam_dung(self):
        self._set_stage('sonha_du_an.task_stage_tam_dung')

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
