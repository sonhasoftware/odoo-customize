import base64
import io

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class IprRequest(models.Model):
    _name = "ipr.request"
    _description = "Internal Purchase Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        string="Mã phiếu",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        default=lambda self: self.env.user.employee_id,
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
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("confirm", "Chờ duyệt"),
            ("approve", "Đã duyệt"),
            ("reject", "Từ chối"),
        ],
        string="Trạng thái",
        default="draft",
        required=True,
        tracking=True,
    )
    line_ids = fields.One2many(
        "ipr.request.line",
        "request_id",
        string="Chi tiết yêu cầu",
        copy=True,
    )
    total_amount = fields.Monetary(
        string="Tổng tiền",
        compute="_compute_total_amount",
        store=True,
        currency_field="currency_id",
        tracking=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt hiện tại",
        tracking=True,
    )
    first_approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt cấp 1",
        tracking=True,
    )
    second_approver_id = fields.Many2one(
        "res.users",
        string="Người duyệt cấp 2",
        tracking=True,
    )
    approval_level = fields.Selection(
        [
            ("none", "Chưa cần duyệt"),
            ("first", "Duyệt cấp 1"),
            ("second", "Duyệt cấp 2"),
            ("done", "Hoàn tất"),
        ],
        string="Cấp duyệt",
        default="none",
        tracking=True,
    )
    is_two_step_approval = fields.Boolean(
        string="Cần duyệt 2 cấp",
        compute="_compute_is_two_step_approval",
        store=True,
    )
    is_multi_company = fields.Boolean(
        string="Khác công ty người dùng",
        compute="_compute_is_multi_company",
    )
    note = fields.Text(string="Ghi chú")

    @api.depends("line_ids.subtotal")
    def _compute_total_amount(self):
        for request in self:
            request.total_amount = sum(request.line_ids.mapped("subtotal"))

    @api.depends("total_amount")
    def _compute_is_two_step_approval(self):
        for request in self:
            request.is_two_step_approval = request.total_amount > 10000000

    @api.depends("company_id")
    def _compute_is_multi_company(self):
        current_company = self.env.company
        for request in self:
            request.is_multi_company = bool(request.company_id and request.company_id != current_company)

    @api.model
    def _get_default_approver(self, employee, company):
        manager_user = employee.parent_id.user_id if employee and employee.parent_id else False
        if manager_user and manager_user.company_id == company:
            return manager_user
        hr_group = self.env.ref("sonha_ipr.group_ipr_manager", raise_if_not_found=False)
        if hr_group:
            users = hr_group.users.filtered(lambda user: company in user.company_ids)
            if users:
                return users[0]
        return False

    @api.model
    def _get_second_approver(self, company, first_approver=False):
        admin_group = self.env.ref("sonha_ipr.group_ipr_admin", raise_if_not_found=False)
        if not admin_group:
            return False
        users = admin_group.users.filtered(lambda user: company in user.company_ids and user != first_approver)
        return users[:1] if users else False

    def _check_company_approver(self, approver, company):
        if approver and company not in approver.company_ids:
            raise ValidationError(_("Người duyệt phải thuộc công ty của phiếu yêu cầu."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("ipr.request") or "New"
        requests = super().create(vals_list)
        for request in requests:
            request.message_post(body=_("Phiếu yêu cầu mua hàng đã được tạo."))
        return requests

    def write(self, vals):
        if 'state' in vals:
            for record in self:
                if record.state != vals.get('state') and not self.env.context.get("ipr_allow_workflow_write"):
                    raise UserError(_("Vui lòng đổi trạng thái bằng các nút nghiệp vụ trên phiếu."))

        protected_fields = {"employee_id", "company_id", "line_ids"}
        if protected_fields.intersection(vals):
            for request in self:
                if request.state != "draft":
                    raise UserError(_("Chỉ được sửa khi phiếu ở trạng thái nháp."))

        return super().write(vals)

    def unlink(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Không được xoá phiếu khi trạng thái khác nháp."))
        return super().unlink()

    def action_confirm(self):
        for request in self:
            if request.state != "draft":
                raise UserError(_("Chỉ phiếu nháp mới được gửi duyệt."))
            if not request.line_ids:
                raise UserError(_("Bạn cần nhập ít nhất một dòng sản phẩm."))
            first_approver = request._get_default_approver(request.employee_id, request.company_id)
            if not first_approver:
                raise UserError(_("Không tìm thấy người duyệt phù hợp cho công ty này."))
            request._check_company_approver(first_approver, request.company_id)
            vals = {
                "state": "confirm",
                "first_approver_id": first_approver.id,
                "approver_id": first_approver.id,
                "approval_level": "first",
            }
            if request.is_two_step_approval:
                second_approver = request._get_second_approver(request.company_id, first_approver)
                if not second_approver:
                    raise UserError(_("Phiếu trên 10 triệu cần người duyệt cấp 2."))
                request._check_company_approver(second_approver, request.company_id)
                vals["second_approver_id"] = second_approver.id
            request.with_context(ipr_allow_workflow_write=True).write(vals)
            activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if activity_type:
                request.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=first_approver.id,
                    summary=_("Duyệt phiếu %s") % request.name,
                    note=_("Vui lòng duyệt phiếu yêu cầu mua hàng."),
                )
            request.message_post(body=_("Phiếu đã được gửi duyệt cho %s.") % first_approver.name)

    def action_open_approval_wizard(self):
        self.ensure_one()
        if self.state != "confirm":
            raise UserError(_("Chỉ phiếu đang chờ duyệt mới được duyệt."))
        if self.approver_id and self.approver_id != self.env.user and not self.env.user.has_group("sonha_ipr.group_ipr_admin"):
            raise UserError(_("Bạn không phải người duyệt hiện tại của phiếu này."))
        return {
            "name": _("Duyệt phiếu mua hàng"),
            "type": "ir.actions.act_window",
            "res_model": "ipr.approval.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_request_id": self.id,
                "default_approver_id": self.approver_id.id if self.approver_id else False,
            },
        }

    def action_reject(self):
        for request in self:
            if request.state not in ("draft", "confirm"):
                raise UserError(_("Chỉ phiếu nháp hoặc đang chờ duyệt mới được từ chối."))
            request.with_context(ipr_allow_workflow_write=True).write({
                "state": "reject",
                "approval_level": "done",
                "approver_id": False,
            })
            request.activity_unlink(["mail.mail_activity_data_todo"])
            request.message_post(body=_("Phiếu đã bị từ chối bởi %s.") % self.env.user.name)

    @api.model
    def get_dashboard_data(self):
        domain = []
        return {
            "total": self.search_count(domain),
            "pending": self.search_count(domain + [("state", "=", "confirm")]),
            "approved": self.search_count(domain + [("state", "=", "approve")]),
            "rejected": self.search_count(domain + [("state", "=", "reject")]),
            "draft": self.search_count(domain + [("state", "=", "draft")]),
        }

    def action_export_excel(self):
        try:
            import xlsxwriter
        except ImportError as error:
            raise UserError(_("Thiếu thư viện xlsxwriter để xuất Excel.")) from error

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        sheet = workbook.add_worksheet("IPR")
        header_format = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        cell_format = workbook.add_format({"border": 1})
        # Nhóm 3 chữ số + hậu tố đ (định dạng quen thuộc khi đọc số tiền VND)
        money_format = workbook.add_format({"border": 1, "num_format": '#,##0 "đ"'})
        headers = [
            "Mã phiếu",
            "Nhân viên",
            "Phòng ban",
            "Công ty",
            "Trạng thái",
            "Người duyệt",
            "Tổng tiền",
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, header_format)
        for row, request in enumerate(self, start=1):
            sheet.write(row, 0, request.name or "", cell_format)
            sheet.write(row, 1, request.employee_id.name or "", cell_format)
            sheet.write(row, 2, request.department_id.name or "", cell_format)
            sheet.write(row, 3, request.company_id.name or "", cell_format)
            sheet.write(row, 4, dict(request._fields["state"].selection).get(request.state, ""), cell_format)
            sheet.write(row, 5, request.approver_id.name or "", cell_format)
            sheet.write_number(row, 6, request.total_amount or 0, money_format)
        sheet.set_column(0, 0, 18)
        sheet.set_column(1, 5, 24)
        sheet.set_column(6, 6, 16)
        workbook.close()
        output.seek(0)
        attachment = self.env["ir.attachment"].create({
            "name": "internal_purchase_requests.xlsx",
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "res_model": self._name,
            "res_id": self[:1].id if self else False,
        })
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }


class IprRequestLine(models.Model):
    _name = "ipr.request.line"
    _description = "Internal Purchase Request Line"
    _order = "request_id, id"

    request_id = fields.Many2one(
        "ipr.request",
        string="Phiếu yêu cầu",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
    )
    quantity = fields.Float(
        string="Số lượng",
        default=1.0,
        required=True,
    )
    price_unit = fields.Monetary(
        string="Đơn giá",
        required=True,
        currency_field="currency_id",
    )
    subtotal = fields.Monetary(
        string="Thành tiền",
        compute="_compute_subtotal",
        store=True,
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        related="request_id.currency_id",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        store=True,
        readonly=True,
    )

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.constrains("quantity")
    def _check_quantity(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_("Số lượng phải lớn hơn 0."))

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.lst_price
