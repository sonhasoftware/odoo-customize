from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class IprRequest(models.Model):
    _name = "ipr.request"
    _description = "Internal Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    # ─── Basic fields ────────────────────────────────────────────────────────
    name = fields.Char(
        string="Mã phiếu",
        readonly=True,
        copy=False,
        default="New",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        default=lambda self: self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid)], limit=1
        ),
        tracking=True,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Phòng ban",
        related="employee_id.department_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Công ty",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )
    date_request = fields.Date(
        string="Ngày yêu cầu",
        default=fields.Date.context_today,
        required=True,
    )
    note = fields.Text(string="Ghi chú")

    # ─── State ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ("draft", "Nháp"),
            ("confirm", "Chờ duyệt"),
            ("approve", "Đã duyệt"),
            ("reject", "Từ chối"),
        ],
        string="Trạng thái",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # ─── Approver ────────────────────────────────────────────────────────────
    approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt",
        tracking=True,
        domain="[('company_ids', 'in', company_id)]",
    )
    approval_note = fields.Text(string="Ghi chú duyệt", copy=False)
    second_approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt cấp 2",
        tracking=True,
        help="Bắt buộc khi tổng tiền > 10.000.000",
    )
    second_approved = fields.Boolean(string="Đã duyệt cấp 2", default=False, copy=False)

    # ─── Lines ───────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        "ipr.request.line",
        "request_id",
        string="Chi tiết yêu cầu",
        copy=True,
    )

    # ─── Compute ─────────────────────────────────────────────────────────────
    total_amount = fields.Float(
        string="Tổng tiền",
        compute="_compute_total_amount",
        store=True,
        digits=(16, 2),
    )
    is_multi_company = fields.Boolean(
        string="Khác công ty",
        compute="_compute_is_multi_company",
        store=True,
    )
    require_two_level = fields.Boolean(
        string="Cần duyệt 2 cấp",
        compute="_compute_require_two_level",
        store=True,
    )

    # ─── Compute methods ─────────────────────────────────────────────────────
    @api.depends("line_ids.subtotal")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("subtotal"))

    @api.depends("company_id")
    def _compute_is_multi_company(self):
        for rec in self:
            rec.is_multi_company = rec.company_id != self.env.company

    @api.depends("total_amount")
    def _compute_require_two_level(self):
        for rec in self:
            rec.require_two_level = rec.total_amount > 10_000_000

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains("line_ids")
    def _check_lines_not_empty(self):
        for rec in self:
            if not rec.line_ids:
                raise ValidationError(
                    _("Phiếu yêu cầu phải có ít nhất 1 dòng sản phẩm.")
                )

    @api.constrains("approver_id", "company_id", "is_multi_company")
    def _check_approver_company(self):
        """Nếu khác company, approver phải thuộc đúng company đó."""
        for rec in self:
            if rec.is_multi_company and rec.approver_id:
                if rec.company_id not in rec.approver_id.company_ids:
                    raise ValidationError(
                        _('Người duyệt "%s" phải thuộc công ty "%s".')
                        % (rec.approver_id.name, rec.company_id.name)
                    )

    # ─── ORM Override ────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("ipr.request") or "New"
                )
        records = super().create(vals_list)
        return records

    def write(self, vals):
        # Không cho chỉnh sửa khi đã approve hoặc reject (trừ admin)
        if not self.env.user.has_group("ipr_purchase.group_ipr_admin"):
            for rec in self:
                if rec.state in ("approve", "reject") and not set(vals.keys()).issubset(
                    {"message_ids", "activity_ids"}
                ):
                    raise UserError(
                        _('Không thể chỉnh sửa phiếu "%s" ở trạng thái "%s".')
                        % (
                            rec.name,
                            dict(rec._fields["state"].selection).get(rec.state),
                        )
                    )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    _(
                        "Chỉ được xóa phiếu ở trạng thái Nháp. "
                        'Phiếu "%s" đang ở trạng thái "%s".'
                    )
                    % (rec.name, dict(rec._fields["state"].selection).get(rec.state))
                )
        return super().unlink()

    # ─── Action buttons ──────────────────────────────────────────────────────
    def action_confirm(self):
        """Xác nhận phiếu → chuyển sang chờ duyệt, auto-assign approver."""
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Phiếu chưa có sản phẩm nào."))

        approver = self._get_auto_approver()
        vals = {"state": "confirm"}
        if approver:
            vals["approver_id"] = approver.id

        self.write(vals)
        self.message_post(
            body=_("Phiếu đã được xác nhận và gửi duyệt. Người duyệt: %s")
            % (self.approver_id.name if self.approver_id else "Chưa xác định"),
        )

    def action_approve(self):
        """Mở wizard duyệt."""
        self.ensure_one()
        return {
            "name": _("Duyệt yêu cầu"),
            "type": "ir.actions.act_window",
            "res_model": "ipr.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
                "default_approver_id": self.approver_id.id,
            },
        }

    def action_reject(self):
        """Từ chối phiếu."""
        self.ensure_one()
        self.write({"state": "reject"})
        self.message_post(body=_("Phiếu đã bị từ chối bởi %s.") % self.env.user.name)

    def action_reset_draft(self):
        """Trả về nháp."""
        self.ensure_one()
        if self.state == "approve":
            raise UserError(_("Không thể reset phiếu đã duyệt."))
        self.write({"state": "draft", "approval_note": False})
        self.message_post(body=_("Phiếu đã được reset về Nháp."))

    # ─── Internal helpers ─────────────────────────────────────────────────────
    def _get_auto_approver(self):
        """
        Tự động gán approver khi confirm:
        - Ưu tiên manager của phòng ban
        - Fallback: user thuộc group Manager
        """
        self.ensure_one()
        if self.department_id and self.department_id.manager_id:
            manager_user = self.department_id.manager_id.user_id
            if manager_user:
                return manager_user
        # Fallback: lấy 1 người trong group manager
        group_manager = self.env.ref(
            "ipr_purchase.group_ipr_manager", raise_if_not_found=False
        )
        if group_manager and group_manager.users:
            return group_manager.users[0]
        return False
