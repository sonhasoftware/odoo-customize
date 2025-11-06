from datetime import datetime

from odoo import models, fields, api


class WizardDKVBTuChoi(models.TransientModel):
    _name = "wizard.dk.vb.tu.choi"
    _description = "Wizard Từ Chối Văn Bản"

    reason = fields.Text("Lý do từ chối", required=True)
    record_id = fields.Many2one("dk.vb.d", string="Bản ghi duyệt", required=True)

    def action_confirm(self):
        self.ensure_one()
        rec = self.record_id

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        link = f"{base_url}/web#id={rec.dk_vb_h.id}&model=dk.vb.h&view_type=form"
        sender_name = rec.dk_vb_h.create_uid.name if rec.create_uid else ""
        partner = self.env['hr.employee'].sudo().search([('user_id', '=', rec.dk_vb_h.create_uid.id)])
        document_no = rec.dk_vb_h.chung_tu or ""
        document_type = rec.dk_vb_h.id_loai_vb.ten or ""
        send_date = datetime.today().strftime("%d/%m/%Y")
        subject = f"Hồ sơ của Anh/Chị từ chối!"

        body = f"""
                <p>Kính gửi Anh/Chị {sender_name},</p>

                <p>Hệ thống xin thông báo hiện đang có 
                <b>{document_type} đã bị từ chối.</b></p>

                <p>Anh/Chị vui lòng truy cập vào hệ thống để xem chi tiết và thực hiện các điều chỉnh cần thiết (nếu có).</p>

                <p><b>Thông tin hồ sơ bị từ chối:</b><br/>
                • <b>Người gửi:</b> {self.env.user.name}<br/>
                • <b>Số văn bản:</b> {document_no}<br/>
                • <b>Loại đơn:</b> <b>{document_type}</b><br/>
                • <b>Ngày gửi:</b> {send_date}<br/>
                • <b>Link phê duyệt:</b> <a href="{link}">Nhấn vào đây để xem văn bản</a></p>

                <p>Trân trọng,<br/>
                Hệ thống Quản lý Văn bản</p>
            """
        mail_values = {
            'subject': subject,
            'body_html': body,
            'email_to': partner.work_email if partner and partner.work_email else "",
        }
        self.env['mail.mail'].sudo().create(mail_values).sudo().send()

        # Gán thông tin
        rec.is_approved = False
        rec.tu_choi = self.reason
        rec.dk_vb_h.nguoi_tu_choi = self.env.user.id
        rec.dk_vb_h.check_write = False
        rec.dk_vb_h.status = 'reject'

        return {'type': 'ir.actions.act_window_close'}
