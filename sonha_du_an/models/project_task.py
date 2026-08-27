from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta, date


class Task(models.Model):
    _inherit = 'project.task'
    _order = 'create_date asc, id asc'

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
    ngay_hoan_thanh = fields.Date("Ngày hoàn thành", store=True, readonly=True)
    so_ngay_pending = fields.Float("Số ngày Pending", store=True)
    ly_do_pending = fields.Text("Lý do Pending", store=True)

    ns_lam = fields.Many2many('res.users', 'ir_ns_lam_group_rel',
                                  'ns_lam_group_rel', 'ns_lam_rel', string='NS làm', store=True)

    chu_so_huu = fields.Many2many('res.users', 'ir_chu_so_huu_group_rel',
                                  'chu_so_huu_group_rel', 'chu_so_huu_rel', string='Chủ sở hữu', store=True)

    trang_thai = fields.Selection([('kt', 'Khởi tạo'), ('run', 'Đang chạy'),
                                   ('ht', 'Hoàn thành'), ('pd', 'Pending')],
                                  string='Trạng thái',
                                  default='kt',
                                  group_expand='_group_expand_trang_thai', store=True)

    ngay_bd_da_cha = fields.Date("Ngày bắt đầu dự án cha", store=True, compute="get_ngay_bat_dau")
    ngay_kt_da_cha = fields.Date("Ngày kêt thúc dự án cha", store=True, compute="get_ngay_bat_dau")
    check_ngay_chay = fields.Date("Check ngày chạy")
    check_ngay_ht = fields.Date("Check ngày HT")
    can_back_state = fields.Boolean(
        string='Có thể trở lại trạng thái',
        compute='_compute_can_back_state',
    )

    @api.depends('trang_thai','check_ngay_chay','check_ngay_ht')
    def _compute_can_back_state(self):

        today = fields.Date.today()

        # Admin luôn có quyền
        is_admin = self.env.user.has_group('base.group_system')

        for record in self:

            # Admin luôn thấy nút
            if is_admin:
                record.can_back_state = True
                continue

            # Mặc định không cho
            record.can_back_state = False

            # =========================
            # ĐANG CHẠY -> KHỞI TẠO
            # =========================
            if record.trang_thai == 'run':

                # Nếu chưa có ngày thì cho phép
                if not record.check_ngay_chay:
                    record.can_back_state = True

                # Chỉ cho phép khi ngày >= hôm nay
                elif record.check_ngay_chay >= today:
                    record.can_back_state = True

            # =========================
            # HOÀN THÀNH -> ĐANG CHẠY
            # =========================
            elif record.trang_thai == 'ht':

                # Nếu chưa có ngày thì cho phép
                if not record.check_ngay_ht:
                    record.can_back_state = True

                # Chỉ cho phép khi ngày >= hôm nay
                elif record.check_ngay_ht >= today:
                    record.can_back_state = True
            elif record.trang_thai == 'pd':
                record.can_back_state = True

    @api.depends('du_an_cha_task_id')
    def get_ngay_bat_dau(self):
        for r in self:
            if r.du_an_cha_task_id and r.du_an_cha_task_id.ngay_bat_dau:
                r.ngay_bd_da_cha = r.du_an_cha_task_id.ngay_bat_dau
            else:
                r.ngay_bd_da_cha = False

            if r.du_an_cha_task_id and r.du_an_cha_task_id.ngay_kt_da:
                r.ngay_kt_da_cha = r.du_an_cha_task_id.ngay_kt_da
            else:
                r.ngay_kt_da_cha = False

    @api.model
    def _group_expand_trang_thai(self, states, domain, order):
        return [
            'kt',
            'run',
            'ht',
            'pd',
        ]

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Lấy task mới nhất
        last_task = self.search(
            [],
            order='id desc',
            limit=1
        )

        if not last_task:
            return res

        # =========================
        # COPY DỮ LIỆU
        # =========================

        # Nội dung công việc
        res['name'] = last_task.name

        # Dự án con
        if 'cap' in self._fields:
            res['cap'] = last_task.cap.id

        # Dự án cha
        if 'du_an_cha_task_id' in self._fields:
            res['du_an_cha_task_id'] = last_task.du_an_cha_task_id.id

        # Số ngày
        if 'so_ngay' in self._fields:
            res['so_ngay'] = last_task.so_ngay

        # Ngày bắt đầu
        if 'ngay_bat_dau' in self._fields:
            res['ngay_bat_dau'] = last_task.ngay_bat_dau

        # Ngày kết thúc
        if 'ngay_ket_thuc' in self._fields:
            res['ngay_ket_thuc'] = last_task.ngay_ket_thuc

        # Ngày hoàn thành
        if 'ngay_hoan_thanh' in self._fields:
            res['ngay_hoan_thanh'] = last_task.ngay_hoan_thanh

        # NS làm - Many2many
        if 'ns_lam' in self._fields:
            res['ns_lam'] = [
                (6, 0, last_task.ns_lam.ids)
            ]

        # Người QLDA - Many2many
        if 'nguoi_qlda' in self._fields:
            res['nguoi_qlda'] = [
                (6, 0, last_task.nguoi_qlda.ids)
            ]

        # Chủ sở hữu
        if 'chu_so_huu' in self._fields:
            res['chu_so_huu'] = [
                (6, 0, last_task.chu_so_huu.ids)
            ]

        return res

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
            if not vals.get('name'):
                raise ValidationError(
                    _("Bạn không được để trống trường Nội dung công việc của nhiệm vụ!")
                )
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
        today = date.today()
        for r in self:
            r.trang_thai = 'run'
            r.check_ngay_chay = today + timedelta(days=3)

    def action_done(self):
        today = date.today()
        for r in self:
            r.trang_thai = 'ht'
            r.ngay_hoan_thanh = today
            r.check_ngay_ht = today + timedelta(days=3)

    def action_reset(self):
        for r in self:
            if r.trang_thai == 'ht':
                r.trang_thai = 'run'
            elif r.trang_thai == 'run':
                r.trang_thai = 'kt'
            elif r.trang_thai == 'pd':
                r.trang_thai = 'run'
            r.ngay_hoan_thanh = False

    def action_tam_dung(self):
        self.ensure_one()

        return {
            'name': 'Pending nhiệm vụ',
            'type': 'ir.actions.act_window',
            'res_model': 'project.task.pending.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_task_id': self.id,
                'default_ly_do_pending': self.ly_do_pending,
                'default_so_ngay_pending': self.so_ngay_pending,
            },
        }
