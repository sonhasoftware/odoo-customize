from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PlanCollaborate(models.Model):
    _name = 'plan.collaborate'

    code = fields.Char("Mã đơn", compute="get_code")
    type_collaborate = fields.Selection([('in', "Trong nước"),
                                         ('out', "Nước ngoài")],
                            string="Loại công tác",)
    total_price = fields.Float("Tổng chi phí(Dự trù)", compute="get_total_price")
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # giay di cong tac

    date = fields.Date("Ngày")
    employee_id = fields.Many2one('hr.employee', string="Họ và tên", compute="get_employee_info")
    department_id = fields.Many2one(related='employee_id.department_id', string="Đơn vị công tác")
    business = fields.Char("Được cử đi công tác tại:")
    gender = fields.Selection([('male', "Nam"),
                               ('female', "Nữ")],
                              string="Giới tính", compute="get_employee_info")
    from_date = fields.Date("Từ ngày", compute="get_date_business")
    to_date = fields.Date("Đến ngày", compute="get_date_business")

    car = fields.Boolean("Công ty cấp xe và lái xe")
    self_drive = fields.Boolean("Công ty cấp xe, tự lái xe")
    drive = fields.Boolean("Công ty cấp lái xe")
    sufficient = fields.Boolean("Tự túc")

    # end
    general_information = fields.One2many('general.information', 'plan_id', string="Thông tin chung")

    plan_detail = fields.One2many('plan.detail', 'plan_id', string="Kế hoạch công tác chi tiết")

    cost_coverage = fields.One2many('cost.coverage', 'plan_id', string="Chi phí được đài thọ")

    cost_estimated = fields.One2many('cost.estimated', 'plan_id', string="Chi phí dự kiến")

    config_id = fields.Many2one('config.approval', string='Chọn bước duyệt')
    step_line_ids = fields.One2many('plan.step', 'plan_id', string="Luồng duyệt áp dụng")
    current_step_label = fields.Char(string="Trạng thái hiện tại", compute="_compute_current_step_label", store=True)

    manager_ids = fields.Many2many('hr.employee', compute='_compute_manager_ids', store=True)

    @api.depends('general_information.employee_id')
    def _compute_manager_ids(self):
        for rec in self:
            managers = self.env['hr.employee']
            for line in rec.general_information:
                if line.employee_id.parent_id:
                    managers |= line.employee_id.parent_id
                if line.employee_id.parent_id.parent_id:
                    managers |= line.employee_id.parent_id.parent_id
            rec.manager_ids = managers

    def action_approve_step(self):
        for record in self:
            current_employee = self.env.user.employee_id
            a = self.env.user

            # Lấy bước chưa duyệt có sequence nhỏ nhất
            steps = record.step_line_ids.filtered(lambda s: not s.status_done)
            if not steps:
                raise ValidationError("Đã duyệt xong.")

            current_sequence = min(steps.mapped('sequence'))
            current_steps = steps.filtered(lambda s: s.sequence == current_sequence)

            # Kiểm tra nếu user hiện tại là 1 trong các người duyệt ở bước này
            step_for_user = current_steps.filtered(lambda s: s.employee_id == current_employee)
            if not step_for_user:
                raise ValidationError("Bạn không phải người duyệt ở bước hiện tại.")

            # Đánh dấu đã duyệt bước của người đó
            step_for_user.status_done = True

    @api.depends('step_line_ids.status_done')
    def _compute_current_step_label(self):
        for record in self:
            # Lấy các bước chưa duyệt, group theo sequence
            steps_by_sequence = {}
            for line in record.step_line_ids:
                if not line.status_done:
                    steps_by_sequence.setdefault(line.sequence, []).append(line)

            if not steps_by_sequence:
                record.current_step_label = "Đã duyệt xong"
            else:
                current_sequence = min(steps_by_sequence.keys())
                current_steps = steps_by_sequence[current_sequence]
                if current_steps:
                    # Lấy trạng thái từ dòng đầu tiên (các bước cùng sequence thường có chung trạng thái)
                    status_name = current_steps[0].status.name if current_steps[0].status else "Không rõ"
                    record.current_step_label = f"Trạng thái hiện tại: {status_name}"
                else:
                    record.current_step_label = "Không rõ trạng thái hiện tại"

    @api.onchange('config_id')
    def _onchange_config_id(self):
        if self.config_id:
            self.step_line_ids = [(5, 0, 0)]
            lines = []
            for line in self.config_id.step_status.sorted('sequence'):
                approval_id = self.get_approval_id(line.approval)
                lines.append((0, 0, {
                    'sequence': line.sequence,
                    'status': line.status.id,
                    'approval': line.approval,
                    'employee_id': approval_id,
                }))
            self.step_line_ids = lines

    def get_approval_id(self, key):
        approval_id = None
        employee = self.env['hr.employee'].sudo().search([
            ('user_id', '=', self.env.user.id)
        ], limit=1)
        if key == 'user':
            approval_id = employee.id
        elif key == 'qlc1':
            approval_id = employee.parent_id.id
        elif key == 'qlc2':
            approval_id = employee.parent_id.parent_id.id
        elif key == 'qlc3':
            approval_id = employee.parent_id.parent_id.parent_id.id
        return approval_id

    def create(self, vals):
        res = super(PlanCollaborate, self).create(vals)

        if not res.config_id:
            # Lấy tất cả các phòng ban từ dòng general_information
            departments = res.general_information.mapped('department_id')
            unique_departments = departments.filtered(lambda d: d)
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', res.create_uid.id)])
            status = self.env['approval.state.plan'].sudo().search([])
            draft = status.filtered(lambda x: x.code_state == 'draft')
            waiting = status.filtered(lambda x: x.code_state == 'waiting')
            done = status.filtered(lambda x: x.code_state == 'done')
            # Trường hợp không có department, bỏ qua
            if not unique_departments:
                return res

            lines = []
            lines.append((0, 0, {
                'sequence': 0,
                'status': draft.id,
                'employee_id': employee.id,
            }))
            sequence = 1
            for dept in unique_departments:
                manager = dept.manager_id
                if not manager:
                    continue  # Nếu không có người quản lý thì bỏ qua

                lines.append((0, 0, {
                    'sequence': sequence,
                    'status': waiting.id,
                    'employee_id': manager.id,
                }))

            lines.append((0, 0, {
                'sequence': sequence + 1,
                'status': done.id,
            }))

            res.step_line_ids = lines

        return res

    # def write(self, vals):
    #     for record in self:
    #         if not vals.get('config_id') and not record.config_id:
    #             # Xóa các bước cũ nếu có
    #             record.step_line_ids.unlink()
    #
    #             # Lấy các phòng ban từ employee_id trong general_information
    #             departments = record.general_information.mapped('employee_id.department_id')
    #             unique_departments = departments.filtered(lambda d: d)
    #
    #             if not unique_departments:
    #                 continue
    #
    #             lines = []
    #             sequence = 0
    #             for dept in unique_departments:
    #                 manager = dept.manager_id
    #                 if not manager:
    #                     continue  # Bỏ qua nếu phòng không có người quản lý
    #
    #                 lines.append((0, 0, {
    #                     'sequence': sequence,
    #                     'employee_id': manager.id,
    #                 }))
    #                 sequence += 1
    #
    #     return super(PlanCollaborate, self).write({'step_line_ids': lines})

    def get_code(self):
        for r in self:
            if r.id:
                r.code = "BM.01 - Cong tac " + str(r.id)
            else:
                r.code = "BM.01 - Cong tac "

    @api.depends('cost_estimated')
    def get_total_price(self):
        for r in self:
            r.total_price = 0
            if r.cost_estimated:
                for price in r.cost_estimated:
                    r.total_price += price.price_vnd

    @api.depends('create_uid')
    def get_employee_info(self):
        for r in self:
            if r.create_uid:
                employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                r.employee_id = employee_id.id if employee_id else None
                r.gender = employee_id.gender if employee_id.gender else None

    @api.depends('plan_detail')
    def get_date_business(self):
        for r in self:
            record_date = self.env['plan.detail'].sudo().search([('plan_id', '=', r.id)], order='time DESC')
            r.from_date = record_date[-1].time if record_date and record_date[-1].time else None
            r.to_date = record_date[0].time if record_date and record_date[0].time else None


class PlanStep(models.Model):
    _name = 'plan.step'
    _order = 'sequence'

    name = fields.Char()
    plan_id = fields.Many2one('plan.collaborate')
    sequence = fields.Integer()
    status = fields.Many2one('approval.state.plan', string="Trạng thái")
    manager_ids = fields.Many2many('hr.employee', related='plan_id.manager_ids', store=False)
    domain_employee_ids = fields.Many2many('hr.employee', compute='_compute_domain_employee_ids', store=False)
    employee_id = fields.Many2one('hr.employee',
                                  string="Người duyệt")
    approval = fields.Selection([
        ('user', 'Người làm đơn'),
        ('qlc1', 'Quản lý cấp 1'),
        ('qlc2', 'Quản lý cấp 2'),
        ('hr', 'Nhân sự(HR)'),
        ('gd', 'Giám đốc'),
        ('qlc3', 'Quản lý cấp 3'),
    ], string="Người duyệt")
    status_done = fields.Boolean(string="Đã duyệt", default=False)

    @api.depends('manager_ids')
    def _compute_domain_employee_ids(self):
        for rec in self:
            rec.domain_employee_ids = rec.manager_ids
