from odoo import api, fields, models, _
from odoo.exceptions import UserError


class IprApprovalWizard(models.TransientModel):
    _name = 'ipr.approval.wizard'
    _description = 'Wizard Duyệt Phiếu IPR'

    request_id = fields.Many2one(
        'ipr.request',
        string='Phiếu yêu cầu',
        required=True,
        readonly=True,
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Người duyệt',
    )
    approval_note = fields.Text(
        string='Ghi chú duyệt',
        required=True,
    )
    total_amount = fields.Float(
        related='request_id.total_amount',
        string='Tổng tiền',
        readonly=True,
    )
    require_two_level = fields.Boolean(
        related='request_id.require_two_level',
        string='Cần duyệt 2 cấp',
        readonly=True,
    )
    second_approver_id = fields.Many2one(
        'res.users',
        string='Người duyệt cấp 2',
    )

    def action_approve(self):
        """Xử lý duyệt phiếu từ wizard."""
        self.ensure_one()
        request = self.request_id

        if request.state != 'confirm':
            raise UserError(_('Chỉ được duyệt phiếu đang ở trạng thái "Chờ duyệt".'))

        # Validate người duyệt 2 cấp nếu cần
        if request.require_two_level and not self.second_approver_id:
            raise UserError(_(
                'Tổng tiền vượt 10.000.000 VNĐ, bắt buộc phải chọn người duyệt cấp 2.'
            ))

        vals = {
            'state': 'approve',
            'approval_note': self.approval_note,
        }
        if self.approver_id:
            vals['approver_id'] = self.approver_id.id
        if self.second_approver_id:
            vals['second_approver_id'] = self.second_approver_id.id
            vals['second_approved'] = True

        request.write(vals)

        # Ghi log vào chatter
        log_msg = _(
            '<b>✅ Phiếu đã được duyệt</b><br/>'
            '<b>Người duyệt:</b> %s<br/>'
            '<b>Ghi chú:</b> %s'
        ) % (self.approver_id.name if self.approver_id else self.env.user.name, self.approval_note)

        if self.second_approver_id:
            log_msg += _('<br/><b>Người duyệt cấp 2:</b> %s') % self.second_approver_id.name

        request.message_post(body=log_msg)

        return {'type': 'ir.actions.act_window_close'}

    def action_reject(self):
        """Từ chối ngay trong wizard."""
        self.ensure_one()
        if not self.approval_note:
            raise UserError(_('Vui lòng nhập lý do từ chối.'))

        self.request_id.write({
            'state': 'reject',
            'approval_note': self.approval_note,
        })
        self.request_id.message_post(
            body=_('<b>❌ Phiếu bị từ chối</b><br/><b>Lý do:</b> %s') % self.approval_note
        )
        return {'type': 'ir.actions.act_window_close'}
