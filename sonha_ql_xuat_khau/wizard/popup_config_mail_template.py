from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


class PopupConfigMailTemplate(models.TransientModel):
    _name = 'popup.config.mail.template'

    person_receive = fields.Many2one('exp.mail.config', string="Người nhận mail", store=True)
    mail_to = fields.Char(string="Gửi tới", compute="compute_mail_to_cc", store=True)
    cc_to = fields.Char(string="CC tới", compute="compute_mail_to_cc", store=True)
    body_mail = fields.Html(string="Nội dung", store=True)
    attach_file = fields.Many2many('ir.attachment',
                                   'exp_mail_temp_file_attachment_rel',
                                   'document_id',
                                   'attachment_id', string="File đính kèm", store=True)
    attach_file_name = fields.Char(string="Tên file đính kèm", store=True)
    contract_id = fields.Many2one('exp.contract', string="Hợp đồng", store=True)
    key_id = fields.Integer(store=True)
    subject = fields.Char(string="Tiêu đề", store=True)
    state_code = fields.Char(store=True)

    def action_send(self):
        state_rule = self.env['exp.state.transition.rule'].sudo().search([('from_state_id', '=', self.contract_id.state_id.id)])
        template = self.env.ref('sonha_ql_xuat_khau.product_request_mail_template').sudo()
        if self.attach_file:
            template.attachment_ids = [(6, 0, self.attach_file.ids)]
        self.contract_id.sudo().write({'state_id': state_rule.to_state_id.id,
                                       'date_state_change': str(datetime.now().date())})
        if self.mail_to:
            template.email_to = self.mail_to.replace(" ", "")
            if self.cc_to:
                template.email_cc = self.cc_to.replace(" ", "")
            template.write({
                'subject': self.subject,
                'body_html': self.body_mail,
            })
            template.send_mail(self.contract_id.id, force_send=True)

    @api.depends('person_receive')
    def compute_mail_to_cc(self):
        for r in self:
            if r.person_receive:
                mail_to_char = ""
                mail_cc_char = ""
                if r.person_receive.mail_to:
                    mail_to_list = [e for e in r.person_receive.mail_to.mapped('work_email') if e]
                    mail_to_char = ','.join(
                        mail_to_list) + "," + r.person_receive.mail_to_char if r.person_receive.mail_to_char else ','.join(
                        mail_to_list)
                elif not r.person_receive.mail_to and r.person_receive.mail_to_char:
                    mail_to_char = r.person_receive.mail_to_char
                if mail_to_char != "":
                    if r.person_receive.mail_cc:
                        mail_cc_list = [e for e in r.person_receive.mail_cc.mapped('work_email') if e]
                        mail_cc_char = ','.join(
                            mail_cc_list) + "," + r.person_receive.mail_cc_char if r.person_receive.mail_cc_char else ','.join(
                            mail_cc_list)
                    elif not r.person_receive.mail_cc and r.person_receive.mail_cc_char:
                        mail_cc_char = r.person_receive.mail_cc_char
                r.mail_to = mail_to_char
                r.cc_to = mail_cc_char

    def action_confirm(self):
        for r in self:
            key_record = self.env['popup.required.document'].sudo().search([('id', '=', r.key_id)])
            key_record.sudo().write({
                'body_mail': r.body_mail,
                'mail_to': r.mail_to if r.mail_to else '',
                'cc_to': r.cc_to if r.cc_to else '',
                'subject': r.subject if r.subject else "Tiêu đề",
            })
            state = key_record.state_id.name.lower() if key_record.state_code not in ['co_bh', 'bill_of_lading'] else key_record.state_id.name
            name = f"Yêu cầu đính kèm file {state}"
            return {
                'name': name,
                'type': 'ir.actions.act_window',
                'res_model': 'popup.required.document',
                'view_mode': 'form',
                'target': 'new',
                'res_id': r.key_id,
            }

    def action_set_default(self):
        for r in self:
            if r.person_receive:
                rule = self.env['exp.state.transition.rule'].sudo().search([('from_state_id', '=', r.contract_id.state_id.id)])
                config_mail_to = self.env['exp.mail.config'].sudo().search([('default_rule', '=', rule.id)])
                if config_mail_to:
                    config_mail_to.default_rule = None
                r.person_receive.sudo().write({'default_rule': rule.id if rule else None})
            else:
                raise ValidationError("Phải chọn người nhận mail mới có thể đặt làm mặc định!")
            key_record = self.env['popup.required.document'].sudo().search([('id', '=', r.key_id)])
            state = key_record.state_id.name.lower() if key_record.state_code not in ['co_bh',
                                                                                      'bill_of_lading'] else key_record.state_id.name
            name = f"Yêu cầu đính kèm file {state}"
            return {
                'name': name,
                'type': 'ir.actions.act_window',
                'res_model': 'popup.required.document',
                'view_mode': 'form',
                'target': 'new',
                'res_id': r.key_id,
            }
