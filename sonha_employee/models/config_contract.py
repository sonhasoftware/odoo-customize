from odoo import models, api, fields


class ConfigContract(models.Model):
    _name = 'config.contract'

    company_id = fields.Many2one('res.company', string="Công ty")
    receiver = fields.Many2many('hr.employee', 'ir_receiver_group_rel',
                                'receiver_group_rel', 'receiver_rel',
                                string='Người nhận mail')
    cc_mail = fields.Many2many('hr.employee', 'ir_cc_mail_group_rel',
                               'cc_mail_group_rel', 'cc_mail_rel',
                               string='CC Mail')
    sent_mail = fields.Boolean("Gửi mail cảnh báo hết hạn")
    auto = fields.Boolean("Tự động duyệt hợp đồng")
    auto_code = fields.Boolean("Tự động sinh mã hợp đồng")
    file = fields.Binary("File")
