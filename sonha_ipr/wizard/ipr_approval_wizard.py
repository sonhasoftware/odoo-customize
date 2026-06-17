from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class IprApprovalWizard(models.TransientModel):
    _name = "ipr.approval.wizard"
    _description = "IPR Approval Wizard"

    request_id = fields.Many2one(
        "ipr.request",
        string="Phiếu yêu cầu",
        required=True,
        readonly=True,
    )
    note = fields.Text(
        string="Ghi chú duyệt",
        required=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string="Chuyển người duyệt",
    )

    def action_submit(self):
        self.ensure_one()
        request = self.request_id
        if request.state != "confirm":
            raise UserError(_("Chỉ phiếu đang chờ duyệt mới được duyệt."))
        if self.approver_id and request.company_id not in self.approver_id.company_ids:
            raise ValidationError(_("Người duyệt được chọn phải thuộc công ty của phiếu yêu cầu."))
        if request.is_two_step_approval and request.approval_level == "first":
            next_approver = self.approver_id or request.second_approver_id
            if not next_approver:
                raise UserError(_("Phiếu này cần người duyệt cấp 2."))
            request.with_context(ipr_allow_workflow_write=True).write({
                "approval_level": "second",
                "approver_id": next_approver.id,
            })
            request.activity_unlink(["mail.mail_activity_data_todo"])
            activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if activity_type:
                request.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=next_approver.id,
                    summary=_("Duyệt cấp 2 phiếu %s") % request.name,
                    note=_("Phiếu đã qua duyệt cấp 1 và cần duyệt cấp 2."),
                )
            request.message_post(
                body=_("Duyệt cấp 1 bởi %(user)s.<br/>Ghi chú: %(note)s<br/>Chuyển cấp 2 cho %(approver)s.") % {
                    "user": self.env.user.name,
                    "note": self.note,
                    "approver": next_approver.name,
                }
            )
            return {"type": "ir.actions.act_window_close"}
        request.with_context(ipr_allow_workflow_write=True).write({
            "state": "approve",
            "approval_level": "done",
            "approver_id": False,
        })
        request.activity_unlink(["mail.mail_activity_data_todo"])
        request.message_post(
            body=_("Phiếu đã được duyệt bởi %(user)s.<br/>Ghi chú: %(note)s") % {
                "user": self.env.user.name,
                "note": self.note,
            }
        )
        return {"type": "ir.actions.act_window_close"}
