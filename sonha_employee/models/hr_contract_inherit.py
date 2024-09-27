from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from lxml import etree
from odoo import models, api


class HrContract(models.Model):
    _inherit = 'hr.contract'

    #
    contract_type_id = fields.Many2one('hr.contract.type', string="Loại hợp đồng", ondelete='cascade')
    employee_code = fields.Char(string="Mã nhân viên", related='employee_id.employee_code')
    mail = fields.Boolean('mail', default=False)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        result = super(HrContract, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar,
                                                             submenu=submenu)
        if view_type == 'form':
            doc = etree.XML(result['arch'])
            state = self.env.context.get('state', self.state)
            for node in doc.xpath("//field[@name='resource_calendar_id']"):
                if state != 'draft':
                    node.set('readonly', '1')
                else:
                    node.set('readonly', '0')
            result['arch'] = etree.tostring(doc, encoding='unicode')
        return result

    def action_confirm(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'open'

    def action_cancel(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'cancel'

    def cancel_confirm(self):
        for r in self:
            if r.state == 'open':
                r.state = 'draft'

    def action_cron_send_warning_mail_method(self):
        now = datetime.now()
        template = self.env.ref('sonha_employee.warning_mail_template')
        if now.day == 1 or now.day == 15:
            if now.day == 1:
                start = now.replace(day=1) + timedelta(hours=7)
                end_date = start + relativedelta(months=1, days=-1)
            else:
                start = now.replace(day=15) + timedelta(hours=7)
                end_date = start + relativedelta(months=1)
            list_contracts = self.env['hr.contract'].sudo().search([('date_start', '>=', start),
                                                                    ('date_end', '<=', end_date),
                                                                    ('state', '=', 'open')])
            list_expired_contract = []
            for contract in list_contracts:
                if contract.mail == False:
                    contract.mail = True
                    expired_contract = str(contract.employee_id.name) + " - " + str(contract.employee_code) + " có hợp đồng " + str(contract.name) + " sắp hết hạn"
                else:
                    expired_contract = str(contract.employee_id.name) + " - " + str(contract.employee_code) + " có hợp đồng " + str(contract.name) + " sắp hết hạn (Đã gửi mail)"
                list_expired_contract.append(expired_contract)
            body_mail = ', '.join(list_expired_contract)
            custom_body = "<p>Kính gửi HR,<br></br>Dưới đây là danh sách những nhân viên sắp hết hạn:<br></br></p>" + body_mail
            if body_mail:
                template.write({
                    'body_html': custom_body
                })
                template.send_mail(contract.id, force_send=True)
