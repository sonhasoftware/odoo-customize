from odoo import models, fields, api
import base64
import io
import pandas as pd
from odoo.exceptions import ValidationError
from datetime import datetime, time, timedelta
import unicodedata


class PopupRequiredDocument(models.TransientModel):
    _name = 'popup.required.document'

    file = fields.Many2many('ir.attachment',
                            'exp_document_file_attachment_rel',
                            'document_id',
                            'attachment_id', string='File đính kèm', store=True)
    file_name = fields.Char(string="Tên file đính kèm", store=True)
    contract_id = fields.Many2one('exp.contract', store=True)
    state_id = fields.Many2one('exp.contract.state', store=True)
    state_code = fields.Char(store=True)
    key = fields.Char(store=True)
    required_file = fields.Boolean(store=True)
    body_mail = fields.Html(store=True)
    mail_to = fields.Char(store=True)
    cc_to = fields.Char(store=True)
    subject = fields.Char(store=True)

    def default_person_receive(self):
        for r in self:
            if not r.mail_to:
                state_rule = self.env['exp.state.transition.rule'].sudo().search([('to_state_id', '=', r.state_id.id)])
                person_receive = self.env['exp.mail.config'].sudo().search([('default_rule', '=', state_rule.id)])
                if person_receive:
                    mail_to_char = ""
                    mail_cc_char = ""
                    body_mail = ""
                    if person_receive.mail_to:
                        mail_to_list = [e for e in person_receive.mail_to.mapped('work_email') if e]
                        mail_to_char = ','.join(
                            mail_to_list) + "," + person_receive.mail_to_char if person_receive.mail_to_char else ','.join(
                            mail_to_list)
                    elif not person_receive.mail_to and person_receive.mail_to_char:
                        mail_to_char = person_receive.mail_to_char
                    if mail_to_char != "":
                        if person_receive.mail_cc:
                            mail_cc_list = [e for e in person_receive.mail_cc.mapped('work_email') if e]
                            mail_cc_char = ','.join(
                                mail_cc_list) + "," + r.person_receive.mail_cc_char if person_receive.mail_cc_char else ','.join(
                                mail_cc_list)
                        elif not person_receive.mail_cc and person_receive.mail_cc_char:
                            mail_cc_char = person_receive.mail_cc_char
                        if r.state_code == 'request':
                            body_mail = f"""
                                Dear anh/chị,<br/><br/>
                                Hợp đồng {r.contract_id.contract_no} có yêu cầu sản xuất các sản phẩm.<br/><br/>
                                Xem chi tiết tại file đính kèm.
                            """
                            sub = f"Yêu cầu sản xuất của hợp đồng {self.contract_id.contract_no}"
                        if r.state_code == 'co_bh':
                            body_mail = f"""
                                Dear anh/chị,<br/><br/>
                                Hợp đồng {r.contract_id.contract_no} có tờ khai.<br/><br/>
                                Xem chi tiết tại file đính kèm.
                            """
                    self.sudo().write({'mail_to': mail_to_char,
                                       'cc_to': mail_cc_char,
                                       'body_mail': body_mail,
                                       'subject': sub})

    def action_mail_infor(self):
        for r in self:
            state_rule = self.env['exp.state.transition.rule'].sudo().search([('to_state_id', '=', r.state_id.id)])
            person_receive = self.env['exp.mail.config'].sudo().search([('default_rule', '=', state_rule.id)])
            body_mail = ""
            sub = "Tiêu đề"
            if r.state_code == 'request':
                sub = f"Yêu cầu sản xuất của hợp đồng {self.contract_id.contract_no}"
                body_mail = f"""
                    Dear anh/chị,<br/><br/>
                    Hợp đồng {r.contract_id.contract_no} có yêu cầu sản xuất các sản phẩm.<br/><br/>
                    Xem chi tiết tại file đính kèm.
                """
            if r.state_code == 'co_bh':
                sub = "Tiêu đề"
                body_mail = f"""
                    Dear anh/chị,<br/><br/>
                    Hợp đồng {r.contract_id.contract_no} có tờ khai.<br/><br/>
                    Xem chi tiết tại file đính kèm.
                """
            return {
                'name': 'Thông tin gửi mail',
                'type': 'ir.actions.act_window',
                'res_model': 'popup.config.mail.template',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_contract_id': r.contract_id.id,
                    'default_key_id': r.id,
                    'default_attach_file': [(6, 0, r.file.ids)],
                    'default_attach_file_name': r.file_name,
                    'default_body_mail': body_mail,
                    'default_subject': sub,
                    'default_person_receive': person_receive.id if person_receive else None,
                    'default_state_code': False,
                },
            }

    def extract_file(self):
        if self.state_code == 'request' and self.key == 'change_stt':
            try:
                file_data = base64.b64decode(self.file)
                file_stream = io.BytesIO(file_data)
                df = pd.read_excel(file_stream)
            except Exception:
                raise ValidationError("File không phải Excel hợp lệ hoặc bị lỗi.")

            required_columns = ['Mã hàng hóa', 'Tên hàng hóa', 'Số lượng', 'Đơn vị tính']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValidationError(f"Thiếu các cột bắt buộc: {', '.join(missing_columns)}")

            self.env['exp.production.order'].sudo().search([('contract_id', '=', self.contract_id.id)]).unlink()
            for index, row in df.iterrows():
                vals = {
                    'product_code': False if pd.isna(row.get('Mã hàng hóa')) else row.get('Mã hàng hóa'),
                    'product_name': False if pd.isna(row.get('Tên hàng hóa')) else row.get('Tên hàng hóa'),
                    'quantity': False if pd.isna(row.get('Số lượng')) else row.get('Số lượng'),
                    'unit': False if pd.isna(row.get('Đơn vị tính')) else row.get('Đơn vị tính'),
                    'contract_id': self.contract_id.id if self.contract_id else None
                }
                self.env['exp.production.order'].sudo().create(vals)

    def remove_accents(self, text):
        text = unicodedata.normalize('NFD', text)
        text = ''.join(
            c for c in text
            if unicodedata.category(c) != 'Mn'
        )
        return text

    def action_confirm(self):
        mail = None
        action_user = self.env.user.id
        mail_from = self.env['hr.employee'].sudo().search([('user_id', '=', action_user)], limit=1).work_email
        if self.key == 'change_stt':
            template = self.env.ref('sonha_ql_xuat_khau.product_request_mail_template').sudo()
            if self.file:
                attachment_ids = []
                for att in self.file:
                    new_att = att.sudo().copy({
                        'name': self.remove_accents(att.name)
                    })
                    attachment_ids.append(new_att.id)
                template.attachment_ids = [(6, 0, attachment_ids)]
            self.env['exp.contract.state.log'].sudo().create({
                'contract_id': self.contract_id.id,
                'from_state_id': self.state_id.id,
                'to_state_id': self.state_id.id,
                'change_by': self.env.user.id,
            })
            self.contract_id.sudo().write({'state_id': self.state_id,
                                           'date_state_change': str(datetime.now().date())})
            if self.mail_to and self.state_code != 'request' and self.state_code != 'co_bh':
                template.email_to = self.mail_to.replace(" ", "")
                if self.cc_to:
                    template.email_cc = self.cc_to.replace(" ", "")
                if mail_from:
                    template.write({
                        'email_from': mail_from,
                    })
                template.write({
                    'subject': self.subject,
                    'body_html': self.body_mail,
                })
                mail = template.send_mail(self.contract_id.id, force_send=True)
            if self.state_code == 'done':
                self.file.sudo().write({
                    'res_id': self.id
                })
                self.contract_id.sudo().write({
                    'mtr_file': [(6, 0, self.file.ids)],
                })
            if self.state_code == 'send':
                self.file.sudo().write({
                    'res_id': self.id
                })
                self.contract_id.sudo().write({
                    'payment_file': [(6, 0, self.file.ids)],
                })
            if self.state_code == 'request' and self.file:
                self.file.sudo().write({
                    'res_id': self.id
                })
                self.contract_id.sudo().write({
                    'product_file': [(6, 0, self.file.ids)],
                    'produce_status': 'draft',
                    'produce_code': '',
                })
                self.default_person_receive()
                if self.mail_to:
                    template.email_to = self.mail_to.replace(" ", "")
                    if self.cc_to:
                        template.email_cc = self.cc_to.replace(" ", "")
                    if mail_from:
                        template.write({
                            'email_from': mail_from,
                        })
                    template.write({
                        'subject': self.subject,
                        'body_html': self.body_mail,
                    })
                    mail = template.send_mail(self.contract_id.id, force_send=True)
                else:
                    raise ValidationError("Chưa được cấu hình người nhận")
        else:
            if self.state_code == 'co_bh' and self.file and self.key == 'co_create':
                self.file.sudo().write({
                    'res_id': self.id
                })
                self.contract_id.sudo().write({
                    'co_file': [(6, 0, self.file.ids)],
                    'co': True if self.file else False,
                    'co_status': 'done' if self.file else 'draft',
                })
            elif self.state_code == 'co_bh' and self.file and self.key == 'bh_create':
                self.file.sudo().write({
                    'res_id': self.id
                })
                self.contract_id.sudo().write({
                    'bh_file': [(6, 0, self.file.ids)],
                    'bh': True if self.file else False,
                    'bh_status': 'done' if self.file else 'draft',
                })
        mail_id = self.env['mail.mail'].browse(mail) if mail else None
        if mail_id:
            if mail_id.state == 'exception':
                now = datetime.now()
                self.env['exp.mail.log'].sudo().create({
                    'contract_id': self.contract_id.id,
                    'note': mail_id.failure_reason,
                    'send_date': now,
                })
