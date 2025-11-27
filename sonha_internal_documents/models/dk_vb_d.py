from odoo import api, fields, models, _
import datetime
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError
import requests
import json


class DKVanBanD(models.Model):
    _name = 'dk.vb.d'

    user_duyet = fields.Many2one('res.users', string="Người duyệt", store=True)

    xu_ly = fields.Many2one('dk.xu.ly', string="Tiến trình xử lý", store=True)

    sn_duyet = fields.Float(string="Số ngày duyệt", compute='get_so_ngay_duyet', readonly=False, store=True)
    sn_pb_duyet = fields.Float(string="Số ngày PB duyệt", store=True)

    # Thời gian duyệt (datetime)
    ngay_bd_duyet = fields.Datetime(string="Ngày bắt đầu duyệt", store=True)
    ngay_duyet = fields.Datetime(string="Ngày duyệt", store=True, readonly=True)

    dk_vb_h = fields.Many2one('dk.vb.h', store=True)

    is_approved = fields.Boolean(default=False)
    can_approve = fields.Boolean(
        string="Có thể duyệt",
        compute="_compute_can_approve",
        store=False
    )
    tu_choi = fields.Text("Lý do từ chối", readonly=True, store=True)

    @api.depends('is_approved', 'dk_vb_h.dk_vb_d.is_approved')
    def _compute_can_approve(self):
        for rec in self:

            # Nếu đã duyệt rồi thì ẩn nút
            if rec.is_approved:
                rec.can_approve = False
                continue

            if rec.dk_vb_h.check_write == False:
                rec.can_approve = False
                continue

            # Nếu không phải người duyệt dòng này → ẩn nút
            if not rec.user_duyet or rec.user_duyet.id != rec.env.uid:
                rec.can_approve = False
                continue

            # Kiểm tra các bước trước đã duyệt hết chưa
            previous_pending = self.env['dk.vb.d'].search_count([
                ('dk_vb_h', '=', rec.dk_vb_h.id),
                ('xu_ly.stt', '<', rec.xu_ly.stt),
                ('is_approved', '=', False),
            ])

            rec.can_approve = previous_pending == 0

    @api.onchange('dk_vb_h', 'xu_ly', 'dk_vb_h.sn_pb', 'dk_vb_h.sn_bdh', 'dk_vb_h.sn_ct')
    @api.depends('dk_vb_h', 'xu_ly', 'dk_vb_h.sn_pb', 'dk_vb_h.sn_bdh', 'dk_vb_h.sn_ct')
    def get_so_ngay_duyet(self):
        for r in self:
            if r.dk_vb_h.sn_pb > 0 and r.xu_ly.stt == 1:
                r.sn_duyet = r.dk_vb_h.sn_pb
            elif r.dk_vb_h.sn_bdh > 0 and r.xu_ly.stt == 2:
                r.sn_duyet = r.dk_vb_h.sn_bdh
            elif r.dk_vb_h.sn_ct > 0 and r.xu_ly.stt == 3:
                r.sn_duyet = r.dk_vb_h.sn_ct
            else:
                pass

    def create(self, vals):
        recs = super(DKVanBanD, self).create(vals)
        for rec in recs:
            self.fill_data_tong_hop(rec)
        return recs

    def write(self, vals):
        for r in self:
            self.env['dk.vb.th'].sudo().search([('dk_vb_d', '=', r.id)]).unlink()
            # self.fill_data_tong_hop(r)
        return super(DKVanBanD, self).write(vals)

    def unlink(self):
        for r in self:
            self.env['dk.vb.th'].sudo().search([('dk_vb_d', '=', r.id)]).unlink()
        return super(DKVanBanD, self).unlink()

    def fill_data_tong_hop(self, rec):
        self.env['dk.vb.th'].sudo().create({
            'dk_vb_d': rec.id or None,
            'dk_vb_h': rec.dk_vb_h.id or None,
            'ngay_ct': str(rec.dk_vb_h.ngay_ct) if rec.dk_vb_h.ngay_ct else None,
            'chung_tu': rec.dk_vb_h.chung_tu or None,
            'ngay_ht': str(rec.dk_vb_h.ngay_ht) if rec.dk_vb_h.ngay_ht else None,
            'dvcs': rec.dk_vb_h.dvcs.id or None,
            'id_loai_vb': rec.dk_vb_h.id_loai_vb.id or None,
            'noi_dung': rec.dk_vb_h.noi_dung or None,
            'tn_pb': rec.dk_vb_h.tn_pb or None,
            'sn_pb': rec.dk_vb_h.sn_pb or None,
            'tn_bdh': rec.dk_vb_h.tn_bdh or None,
            'sn_bdh': rec.dk_vb_h.sn_bdh or None,
            'tn_ct': rec.dk_vb_h.tn_ct or None,
            'sn_ct': rec.dk_vb_h.sn_ct or None,
            'user_duyet': rec.user_duyet.id or None,
            'xu_ly': rec.xu_ly.id or None,
            'sn_duyet': rec.sn_duyet or None,
            'sn_pb_duyet': rec.sn_pb_duyet or None,
            'ngay_bd_duyet': str(rec.ngay_bd_duyet) if rec.ngay_bd_duyet else None,
            'ngay_duyet': str(rec.ngay_duyet) if rec.ngay_duyet else None,
        })

    def action_confirm(self):
        for r in self:
            r.ngay_duyet = datetime.datetime.now()
            self.fill_ngay_bd_duyet(r)
            r.is_approved = True

            current_stt = r.xu_ly.stt

            # Tìm tất cả người duyệt của cùng bước hiện tại (chưa duyệt)
            remaining_in_step = self.sudo().search([
                ('dk_vb_h', '=', r.dk_vb_h.id),
                ('xu_ly.stt', '=', current_stt),
                ('is_approved', '=', False),
                ('id', '!=', r.id)
            ])
            if remaining_in_step:
                recipients = []
            else:
                next_stt = current_stt + 1
                next_step_records = self.sudo().search([
                    ('dk_vb_h', '=', r.dk_vb_h.id),
                    ('xu_ly.stt', '=', next_stt),
                    ('is_approved', '=', False)
                ])
                recipients = next_step_records.mapped('user_duyet.employee_ids')
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            if recipients:
                link = f"{base_url}/web#id={r.id}&model=dk.vb.h&view_type=form"
                sender_name = r.create_uid.name if r.create_uid else ""
                document_no = r.chung_tu or ""
                document_type = r.id_loai_vb.ten or ""
                send_date = r.create_date.strftime("%d/%m/%Y") if r.create_date else ""
                for partner in recipients:
                    subject = f"Hồ sơ cần Anh/Chị phê duyệt"

                    body = f"""
                            <p>Kính gửi Anh/Chị {partner.name},</p>

                            <p>Hệ thống xin thông báo hiện đang có 
                            <b>{document_type}</b> đang chờ Anh/Chị xem xét và phê duyệt.</p>

                            <p>Anh/Chị vui lòng truy cập vào hệ thống để kiểm tra và xử lý đơn trong thời gian sớm nhất,
                            nhằm đảm bảo tiến độ công việc.</p>

                            <p><b>Thông tin đơn phê duyệt:</b><br/>
                            • <b>Tóm tắt văn bản:</b><br/>
                            <p>{r.noi_dung_tom_tat}</p>
                            • <b>Người gửi:</b> {sender_name}<br/>
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
                        'email_to': partner.work_email,
                    }
                    self.env['mail.mail'].sudo().create(mail_values).sudo().send()
                    self.noti_manager_action(r, partner)

            menu_id = self.env.ref('sonha_internal_documents.menu_dk_vb_all').id
            action_id = self.env.ref('sonha_internal_documents.action_van_ban_all').id

            url = f"{base_url}/web#id={r.dk_vb_h.id}&menu_id={menu_id}&action={action_id}&model=dk.vb.h&view_type=form"

            return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'self',
            }

    def action_cancel(self):
        for r in self:
            self.ensure_one()
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.dk.vb.tu.choi',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_record_id': r.id,
                },
            }

    def fill_ngay_bd_duyet(self, rec):
        current_stt = rec.xu_ly.stt

        # Tìm tất cả người duyệt của cùng bước hiện tại (chưa duyệt)
        remaining_in_step = self.sudo().search([
            ('dk_vb_h', '=', rec.dk_vb_h.id),
            ('xu_ly.stt', '=', current_stt),
            ('is_approved', '=', False),
            ('id', '!=', rec.id)
        ])

        # Nếu vẫn còn người chưa duyệt trong bước này -> dừng
        if remaining_in_step:
            next_step_records = []
        else:
            next_stt = current_stt + 1
            next_step_records = self.sudo().search([
                ('dk_vb_h', '=', rec.dk_vb_h.id),
                ('xu_ly.stt', '=', next_stt),
                ('is_approved', '=', False)
            ])

            for r in next_step_records:
                r.ngay_bd_duyet = datetime.datetime.now()

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
                   'datetime': str(datetime.datetime.now()),
                   'data': data_text
               })
        except Exception as e:
            return {"error": str(e)}

    def noti_manager_action(self, record, employee_id):
        employee_id = self.env['hr.employee'].sudo().search([('id', '=', employee_id.id)])
        data_text = str(record.id) + "#" + str(employee_id.user_id.id) + "#" + str(employee_id.id) + "#" + str(
            record.chung_tu) + "#6#" + str(employee_id.user_id.name)
        self.send_fcm_notification(
            title="Sơn Hà Văn Bản",
            content="Văn bản " + str(record.chung_tu) + " đang chờ Anh/Chị xem xét và phê duyệt!",
            token=employee_id.user_id.token,
            user_id=employee_id.user_id.id,
            type=6,
            employee_id=employee_id.id,
            application_id=str(record.id),
            data_text=data_text
        )

    def sent_mail_noti(self, r):
        current_stt = r.xu_ly.stt

        # Tìm tất cả người duyệt của cùng bước hiện tại (chưa duyệt)
        remaining_in_step = self.sudo().search([
            ('dk_vb_h', '=', r.dk_vb_h.id),
            ('xu_ly.stt', '=', current_stt),
            ('is_approved', '=', False),
            ('id', '!=', r.id)
        ])
        if remaining_in_step:
            recipients = []
        else:
            next_stt = current_stt + 1
            next_step_records = self.sudo().search([
                ('dk_vb_h', '=', r.dk_vb_h.id),
                ('xu_ly.stt', '=', next_stt),
                ('is_approved', '=', False)
            ])
            users = next_step_records.mapped('user_duyet')
            recipients = self.env['hr.employee'].sudo().search([('user_id', 'in', users.ids)])
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        if recipients:
            link = f"{base_url}/web#id={r.id}&model=dk.vb.h&view_type=form"
            sender_name = r.create_uid.name if r.create_uid else ""
            document_no = r.chung_tu or ""
            document_type = r.id_loai_vb.ten or ""
            send_date = r.create_date.strftime("%d/%m/%Y") if r.create_date else ""
            for partner in recipients:
                subject = f"Hồ sơ cần Anh/Chị phê duyệt"

                body = f"""
                        <p>Kính gửi Anh/Chị {partner.name},</p>

                        <p>Hệ thống xin thông báo hiện đang có 
                        <b>{document_type}</b> đang chờ Anh/Chị xem xét và phê duyệt.</p>

                        <p>Anh/Chị vui lòng truy cập vào hệ thống để kiểm tra và xử lý đơn trong thời gian sớm nhất,
                        nhằm đảm bảo tiến độ công việc.</p>

                        <p><b>Thông tin đơn phê duyệt:</b><br/>
                        • <b>Tóm tắt văn bản:</b><br/>
                        <p>{r.noi_dung_tom_tat}</p>
                        • <b>Người gửi:</b> {sender_name}<br/>
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
                    'email_to': partner.work_email,
                }
                self.env['mail.mail'].sudo().create(mail_values).sudo().send()
                self.noti_manager_action(r, partner)

    def sent_mail_user_reject(self, rec):
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
                   'datetime': str(datetime.datetime.now()),
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

