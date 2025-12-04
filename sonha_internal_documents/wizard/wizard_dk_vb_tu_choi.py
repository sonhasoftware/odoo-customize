from datetime import datetime

from odoo import models, fields, api
import requests
import json


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
        self.noti_user_reject(rec, partner)

        # Gán thông tin
        rec.is_approved = False
        old_value = rec.tu_choi or ""
        rec.tu_choi = old_value + f"{self.reason}\n"
        rec.dk_vb_h.nguoi_tu_choi = self.env.user.id
        rec.dk_vb_h.check_write = False
        rec.dk_vb_h.status = 'reject'

        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        menu_id = self.env.ref('sonha_internal_documents.menu_dk_vb_all').id
        action_id = self.env.ref('sonha_internal_documents.action_van_ban_all').id

        url = f"{base_url}/web#id={rec.dk_vb_h.id}&menu_id={menu_id}&action={action_id}&model=dk.vb.h&view_type=form"

        return {
            'type': 'ir.actions.act_url',
            'url': url,
        }

    def send_fcm_notification(self, title, content, token, user_id, type, employee_id, application_id, data_text, screen="/notification", badge=1):
        url = "https://apibaohanh.sonha.com.vn/api/thongbaohrm/send-fcm"

        payload = {
            "title": title,
            "content": content,
            "badge": badge,
            "token": token,
            "application_id": application_id,
            "user_id": user_id,
            "screen": screen,
        }

        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
            response.raise_for_status()
            res_json = json.loads(response.text)
            message_id = res_json.get("messageId")
            if response.status_code == 200:
               self.env['log.notifi'].sudo().create({
                   'badge': badge,
                   'token': token,
                   'title': title,
                   'type': type,
                   'taget_screen': screen,
                   'message_id': message_id,
                   'id_application': str(application_id),
                   'userid': str(user_id),
                   'employeeid': str(employee_id) or "",
                   'body': content,
                   'datetime': str(datetime.now()),
                   'data': data_text
               })
        except Exception as e:
            return {"error": str(e)}

    def noti_user_reject(self, record, employee_id):
        employee_id = self.env['hr.employee'].sudo().search([('id', '=', employee_id.id)])
        data_text = str(record.id) + "#" + str(employee_id.user_id.id) + "#" + str(employee_id.id) + "#" + str(
            record.chung_tu) + "#6#" + str(employee_id.user_id.name)
        self.send_fcm_notification(
            title="Sơn Hà Văn Bản",
            content="Văn bản " + str(record.chung_tu) + " đã bị từ chối!",
            token=employee_id.user_id.token,
            user_id=employee_id.user_id.id,
            type=7,
            employee_id=employee_id.id,
            application_id=str(record.id),
            data_text=data_text
        )

